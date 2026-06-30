"""Composition root — register thin ``(ctx, payload)`` plane wrappers.

The ONLY plane-aware messaging module. Importing it registers every catalog
op (contract §5; impl plan §1). Plane logic is not moved — wrappers adapt.

Composition roots (dashboard server, workflows, CLI, tests) must
``import warehouse.messaging.handlers`` to register before dispatching.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from warehouse.config import get_settings
from warehouse.data.ingest.runner import IngestRunSummary, run_custodian_ingest
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.analyst import (
    AttributionReport,
    evaluate_attribution,
)
from warehouse.decision.approval.service import (
    ApprovalRequestView,
    create_approval_request,
    create_report_approval_request,
    update_approval_status,
)
from warehouse.decision.constraints import evaluate_lot_sell_allowed
from warehouse.decision.ips.monitor import (
    IpsDriftReport,
    build_ips_drift_report_from_views,
)
from warehouse.decision.optimizer import OptimizationResult
from warehouse.decision.optimizer.heuristics import run_tax_aware_optimizer
from warehouse.decision.optimizer.rebalance import run_mv_rebalance
from warehouse.decision.optimizer.runner import (
    OptimizationRunView,
    persist_optimization,
)
from warehouse.decision.pm import score_pm_axioms
from warehouse.decision.tax.scenarios import (
    TaxScenarioResult,
    evaluate_tax_scenario,
)
from warehouse.execution.oms.service import stage_orders_from_approval
from warehouse.execution.reconciliation.service import reconcile_ingest
from warehouse.messaging.core import dispatch_typed, register
from warehouse.messaging.models import DispatchContext, Kind, Message
from warehouse.messaging.payloads import (
    AdviceBundle,
    ApprovalCreatePayload,
    ApprovalDecidePayload,
    AttributionEvaluatePayload,
    IngestRunPayload,
    LedgerPositionsPayload,
    OptimizePayload,
    OptimizerPersistPayload,
    OrdersStagePayload,
    PmAdvisePayload,
    PolicyCheckPayload,
    PositionSet,
    ReconcilePayload,
    ReconcileResult,
    ReportBuildPayload,
    RiskEvaluatePayload,
    StagedOrders,
    TaxScenarioPayload,
    TradeValidatePayload,
    TradeValidation,
)
from warehouse.reporting.report_writer.models import WrittenHouseholdReport
from warehouse.reporting.report_writer.writer import (
    build_and_write_household_reports,
)
from warehouse.research.risk import evaluate_risk
from warehouse.research.risk.models import RiskResult
from warehouse.research.risk.scenarios import assumptions_for

_R = TypeVar("_R", bound=BaseModel)


# --- QUERY ------------------------------------------------------------------


def _ledger_positions(
    ctx: DispatchContext, p: LedgerPositionsPayload
) -> PositionSet:
    return PositionSet(
        positions=list_lot_positions(
            ctx.require_session(), household_id=p.household_id
        )
    )


# --- EVALUATE (pure — ctx ignored, never touches the session) ---------------


def _risk_evaluate(ctx: DispatchContext, p: RiskEvaluatePayload) -> RiskResult:
    return evaluate_risk(p.request, p.manifest)


def _policy_check(
    ctx: DispatchContext, p: PolicyCheckPayload
) -> IpsDriftReport:
    return build_ips_drift_report_from_views(
        p.household_id, p.positions, p.ips
    )


def _optimizer_propose(
    ctx: DispatchContext, p: OptimizePayload
) -> OptimizationResult:
    # Both engines run behind the one op (no new atomic op — S1): v0 TLH
    # ``trades`` unchanged + the additive po0 advisory ``rebalance`` (§B.1).
    # Frozen result → carry rebalance via model_copy, never post-hoc assign.
    result = run_tax_aware_optimizer(p.household_id, p.positions, p.ips)
    rebalance = run_mv_rebalance(p.positions, p.ips)
    return result.model_copy(update={"rebalance": rebalance})


def _trade_validate(
    ctx: DispatchContext, p: TradeValidatePayload
) -> TradeValidation:
    allowed, binding = evaluate_lot_sell_allowed(p.lot, p.ips)
    return TradeValidation(allowed=allowed, binding=binding)


def _tax_scenario(
    ctx: DispatchContext, p: TaxScenarioPayload
) -> TaxScenarioResult:
    return evaluate_tax_scenario(p.positions, p.overlays)


def _attribution_evaluate(
    ctx: DispatchContext, p: AttributionEvaluatePayload
) -> AttributionReport:
    settings = get_settings()
    # Shipped base-regime class-expected returns are the attribution mechanism.
    return evaluate_attribution(
        p.positions,
        assumptions_for("base").class_expected_return,
        household_id=p.household_id,
        as_of=p.as_of_date or date.today(),
        config_version=settings.analyst_config_version,
        min_holding_years=Decimal(str(settings.analyst_min_holding_years)),
    )


# --- EVALUATE composite — the Portfolio Manager tier (§4.1) ------------------


def _pm_advise(ctx: DispatchContext, p: PmAdvisePayload) -> AdviceBundle:
    """Pure advisory fan-out: nest-dispatch EVALUATE ops with the same trace.

    Mutates nothing — never touches ``ctx.session`` (each child is pure).
    """
    cid = ctx.correlation_id

    def _eval(op: str, payload: BaseModel, result_type: type[_R]) -> _R:
        return dispatch_typed(
            ctx,
            Message(
                op=op,
                kind=Kind.EVALUATE,
                payload=payload,
                correlation_id=cid,
                household_id=p.household_id,
            ),
            result_type,
        )

    risk = _eval(
        "risk.evaluate",
        RiskEvaluatePayload(request=p.request, manifest=p.manifest),
        RiskResult,
    )
    drift = _eval(
        "policy.check",
        PolicyCheckPayload(
            household_id=p.household_id, positions=p.positions, ips=p.ips
        ),
        IpsDriftReport,
    )
    proposal = _eval(
        "optimizer.propose",
        OptimizePayload(
            household_id=p.household_id, positions=p.positions, ips=p.ips
        ),
        OptimizationResult,
    )
    attribution = _eval(
        "attribution.evaluate",
        AttributionEvaluatePayload(
            household_id=p.household_id,
            positions=p.positions,
            as_of_date=p.as_of_date,
        ),
        AttributionReport,
    )
    tax = _eval(
        "tax.scenario",
        TaxScenarioPayload(positions=p.positions, overlays=p.tax_overlays),
        TaxScenarioResult,
    )
    bundle = AdviceBundle(
        risk=risk,
        proposal=proposal,
        tax=tax,
        drift=drift,
        attribution=attribution,
    )
    narrative = score_pm_axioms(bundle, p, correlation_id=cid)
    return bundle.model_copy(update={"narrative": narrative})


# --- COMMAND (gated + audited; uses ctx.session + ctx.actor_id) -------------


def _ingest_run(ctx: DispatchContext, p: IngestRunPayload) -> IngestRunSummary:
    return run_custodian_ingest(
        ctx.require_session(),
        Path(p.path),
        custodian_id=p.custodian_id,
        household_id=p.household_id,
        actor_id=ctx.actor_id,
    )


def _ledger_reconcile(
    ctx: DispatchContext, p: ReconcilePayload
) -> ReconcileResult:
    return ReconcileResult(
        breaks=reconcile_ingest(
            ctx.require_session(),
            p.ingest_run_id,
            household_id=p.household_id,
            actor_id=ctx.actor_id,
        )
    )


def _optimizer_persist(
    ctx: DispatchContext, p: OptimizerPersistPayload
) -> OptimizationRunView:
    # queue_approval=False: persisting is just persisting. The approval is a
    # separate `approval.create` op (no fused persist+queue — S2).
    return persist_optimization(
        ctx.require_session(),
        p.result,
        input_snapshot_id=p.input_snapshot_id,
        actor_id=ctx.actor_id,
        queue_approval=False,
    )


def _approval_create(
    ctx: DispatchContext, p: ApprovalCreatePayload
) -> ApprovalRequestView:
    # Payload validator guarantees exactly one subject is set.
    if p.report_snapshot_id is not None:
        return create_report_approval_request(
            ctx.require_session(),
            report_snapshot_id=p.report_snapshot_id,
            household_id=p.household_id,
        )
    assert p.optimization_run_id is not None  # XOR validator
    return create_approval_request(
        ctx.require_session(), p.optimization_run_id, p.household_id
    )


def _approval_decide(
    ctx: DispatchContext, p: ApprovalDecidePayload
) -> ApprovalRequestView:
    return update_approval_status(
        ctx.require_session(),
        p.request_id,
        status=p.status,
        reviewer_id=p.reviewer_id,
    )


def _orders_stage(ctx: DispatchContext, p: OrdersStagePayload) -> StagedOrders:
    return StagedOrders(
        orders=stage_orders_from_approval(
            ctx.require_session(),
            p.approval_request_id,
            actor_id=ctx.actor_id,
        )
    )


def _report_build(
    ctx: DispatchContext, p: ReportBuildPayload
) -> WrittenHouseholdReport:
    return build_and_write_household_reports(
        ctx.require_session(),
        p.household_id,
        period_label=p.period_label,
        as_of_date=p.as_of_date,
        actor_id=ctx.actor_id,
    )


# --- registration (import side effect) --------------------------------------

register(
    "ledger.positions",
    LedgerPositionsPayload,
    _ledger_positions,
    Kind.QUERY,
)
register("risk.evaluate", RiskEvaluatePayload, _risk_evaluate, Kind.EVALUATE)
register("policy.check", PolicyCheckPayload, _policy_check, Kind.EVALUATE)
register(
    "optimizer.propose",
    OptimizePayload,
    _optimizer_propose,
    Kind.EVALUATE,
)
register(
    "trade.validate",
    TradeValidatePayload,
    _trade_validate,
    Kind.EVALUATE,
)
register("tax.scenario", TaxScenarioPayload, _tax_scenario, Kind.EVALUATE)
register(
    "attribution.evaluate",
    AttributionEvaluatePayload,
    _attribution_evaluate,
    Kind.EVALUATE,
)
register("pm.advise", PmAdvisePayload, _pm_advise, Kind.EVALUATE)
register("ingest.run", IngestRunPayload, _ingest_run, Kind.COMMAND)
register(
    "ledger.reconcile",
    ReconcilePayload,
    _ledger_reconcile,
    Kind.COMMAND,
)
register(
    "optimizer.persist",
    OptimizerPersistPayload,
    _optimizer_persist,
    Kind.COMMAND,
)
register(
    "approval.create",
    ApprovalCreatePayload,
    _approval_create,
    Kind.COMMAND,
)
register(
    "approval.decide",
    ApprovalDecidePayload,
    _approval_decide,
    Kind.COMMAND,
)
register("orders.stage", OrdersStagePayload, _orders_stage, Kind.COMMAND)
register("report.build", ReportBuildPayload, _report_build, Kind.COMMAND)
