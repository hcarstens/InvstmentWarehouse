"""m1 — coordinator: pm.advise purity + correlation; full rebalance loop."""

from collections.abc import Iterator

import pytest

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.approval import ApprovalStatus
from warehouse.decision.ips.monitor import build_ips_drift_report_from_views
from warehouse.decision.ips.store import load_ips
from warehouse.execution.oms import OrderStatus
from warehouse.execution.oms.service import update_order_status
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging import (
    REGISTRY,
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
    observability,
)
from warehouse.messaging.payloads import (
    AdviceBundle,
    ApprovalCreatePayload,
    ApprovalDecidePayload,
    LedgerPositionsPayload,
    OptimizePayload,
    OptimizerPersistPayload,
    OrdersStagePayload,
    PmAdvisePayload,
    PolicyCheckPayload,
)
from warehouse.research.risk.models import RiskHorizon, RiskRequest
from warehouse.research.risk.synthetic import rung

DEMO = DEMO_HOUSEHOLD_ID


@pytest.fixture
def seeded() -> Iterator[None]:
    bootstrap_database(seed=True)
    yield


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    snapshot = dict(REGISTRY)
    observability.clear()
    yield
    REGISTRY.clear()
    REGISTRY.update(snapshot)
    observability.clear()


class _Poison:
    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"pm.advise touched session.{name}")


def test_pm_advise_pure_and_propagates_correlation(seeded: None) -> None:
    with session_scope() as s:
        positions = list_lot_positions(s, household_id=DEMO)
        ips = load_ips(s, DEMO)
        assert ips is not None

    seen: list[str] = []

    def _spy(ctx: DispatchContext, p: PolicyCheckPayload) -> object:
        seen.append(ctx.correlation_id)
        return build_ips_drift_report_from_views(
            p.household_id, p.positions, p.ips
        )

    # Override policy.check with a spy (restored by the autouse fixture).
    REGISTRY["policy.check"] = (PolicyCheckPayload, _spy, Kind.EVALUATE)

    ctx = DispatchContext(session=_Poison())  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="pm.advise",
            kind=Kind.EVALUATE,
            payload=PmAdvisePayload(
                household_id=DEMO,
                positions=positions,
                ips=ips,
                manifest=rung(1),
                request=RiskRequest(horizon=RiskHorizon.parse("5y")),
            ),
            correlation_id="trace-1",
            household_id=DEMO,
        ),
    )
    assert isinstance(out, AdviceBundle)
    # All four legs populated — nothing mutated (poisoned session).
    assert out.risk.report is not None
    assert out.proposal.config_version
    assert out.tax.baseline_tax is not None
    assert out.drift.household_id == DEMO
    # The nested op saw the inbound trace.
    assert seen == ["trace-1"]


def test_rebalance_loop_through_dispatch(seeded: None) -> None:
    with session_scope() as s:
        ctx = DispatchContext(session=s, actor_id="advisor")

        def call(op: str, kind: Kind, payload: object) -> object:
            return dispatch_message(
                ctx,
                Message(
                    op=op,
                    kind=kind,
                    payload=payload,  # type: ignore[arg-type]
                    correlation_id="loop-1",
                    household_id=DEMO,
                ),
            )

        positions = call(
            "ledger.positions",
            Kind.QUERY,
            LedgerPositionsPayload(household_id=DEMO),
        ).positions
        ips = load_ips(s, DEMO)
        assert ips is not None
        proposal = call(
            "optimizer.propose",
            Kind.EVALUATE,
            OptimizePayload(household_id=DEMO, positions=positions, ips=ips),
        )
        run_view = call(
            "optimizer.persist",
            Kind.COMMAND,
            OptimizerPersistPayload(
                result=proposal, input_snapshot_id="snap"
            ),
        )
        appr = call(
            "approval.create",
            Kind.COMMAND,
            ApprovalCreatePayload(
                optimization_run_id=run_view.run_id, household_id=DEMO
            ),
        )
        call(
            "approval.decide",
            Kind.COMMAND,
            ApprovalDecidePayload(
                request_id=appr.request_id,
                status=ApprovalStatus.APPROVED,
                reviewer_id="advisor",
            ),
        )
        staged = call(
            "orders.stage",
            Kind.COMMAND,
            OrdersStagePayload(approval_request_id=appr.request_id),
        )
        assert staged.orders
        filled = update_order_status(
            s,
            staged.orders[0].order_id,
            status=OrderStatus.FILLED,
            actor_id="advisor",
        )
    assert filled.status == OrderStatus.FILLED.value
    assert any(e.op == "order.filled" for e in observability.recent_events())
