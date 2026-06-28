"""Composition root — register thin ``(ctx, payload)`` plane wrappers.

The ONLY plane-aware messaging module. Importing it registers every catalog
op (contract §5; impl plan §1). Plane logic is not moved — wrappers adapt.

Composition roots (dashboard server, workflows, CLI, tests) must
``import warehouse.messaging.handlers`` to register before dispatching.
"""

from __future__ import annotations

from pathlib import Path

from warehouse.data.ingest.runner import IngestRunSummary, run_custodian_ingest
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.approval.service import (
    ApprovalRequestView,
    create_approval_request,
    update_approval_status,
)
from warehouse.decision.constraints import evaluate_lot_sell_allowed
from warehouse.decision.ips.monitor import (
    IpsDriftReport,
    build_ips_drift_report_from_views,
)
from warehouse.decision.optimizer import OptimizationResult
from warehouse.decision.optimizer.heuristics import run_tax_aware_optimizer
from warehouse.decision.optimizer.runner import (
    OptimizationRunView,
    persist_optimization,
)
from warehouse.execution.oms.service import stage_orders_from_approval
from warehouse.execution.reconciliation.service import reconcile_ingest
from warehouse.messaging.core import register
from warehouse.messaging.models import DispatchContext, Kind
from warehouse.messaging.payloads import (
    ApprovalCreatePayload,
    ApprovalDecidePayload,
    IngestRunPayload,
    LedgerPositionsPayload,
    OptimizePayload,
    OptimizerPersistPayload,
    OrdersStagePayload,
    PolicyCheckPayload,
    PositionSet,
    ReconcilePayload,
    ReconcileResult,
    RiskEvaluatePayload,
    StagedOrders,
    TradeValidatePayload,
    TradeValidation,
)
from warehouse.research.risk import evaluate_risk
from warehouse.research.risk.models import RiskResult

# --- QUERY ------------------------------------------------------------------


def _ledger_positions(
    ctx: DispatchContext, p: LedgerPositionsPayload
) -> PositionSet:
    return PositionSet(
        positions=list_lot_positions(ctx.session, household_id=p.household_id)
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
    return run_tax_aware_optimizer(p.household_id, p.positions, p.ips)


def _trade_validate(
    ctx: DispatchContext, p: TradeValidatePayload
) -> TradeValidation:
    allowed, binding = evaluate_lot_sell_allowed(p.lot, p.ips)
    return TradeValidation(allowed=allowed, binding=binding)


# --- COMMAND (gated + audited; uses ctx.session + ctx.actor_id) -------------


def _ingest_run(
    ctx: DispatchContext, p: IngestRunPayload
) -> IngestRunSummary:
    return run_custodian_ingest(
        ctx.session,
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
            ctx.session,
            p.ingest_run_id,
            household_id=p.household_id,
            actor_id=ctx.actor_id,
        )
    )


def _optimizer_persist(
    ctx: DispatchContext, p: OptimizerPersistPayload
) -> OptimizationRunView:
    return persist_optimization(
        ctx.session,
        p.result,
        input_snapshot_id=p.input_snapshot_id,
        actor_id=ctx.actor_id,
    )


def _approval_create(
    ctx: DispatchContext, p: ApprovalCreatePayload
) -> ApprovalRequestView:
    return create_approval_request(
        ctx.session, p.optimization_run_id, p.household_id
    )


def _approval_decide(
    ctx: DispatchContext, p: ApprovalDecidePayload
) -> ApprovalRequestView:
    return update_approval_status(
        ctx.session,
        p.request_id,
        status=p.status,
        reviewer_id=p.reviewer_id,
    )


def _orders_stage(
    ctx: DispatchContext, p: OrdersStagePayload
) -> StagedOrders:
    return StagedOrders(
        orders=stage_orders_from_approval(
            ctx.session, p.approval_request_id, actor_id=ctx.actor_id
        )
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
