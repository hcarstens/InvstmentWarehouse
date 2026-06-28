"""m0b — handler wrappers: round-trip == direct call; EVALUATE purity (§5)."""

from collections.abc import Iterator

import pytest

import warehouse.messaging.handlers  # noqa: F401 — registers catalog ops
from warehouse.config import repo_root
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.approval import ApprovalStatus
from warehouse.decision.approval.service import list_approval_requests
from warehouse.decision.constraints import evaluate_lot_sell_allowed
from warehouse.decision.ips.monitor import build_ips_drift_report_from_views
from warehouse.decision.ips.store import load_ips
from warehouse.decision.optimizer.heuristics import run_tax_aware_optimizer
from warehouse.decision.optimizer.runner import run_and_persist_optimizer
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging import (
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
)
from warehouse.messaging.payloads import (
    IngestRunPayload,
    LedgerPositionsPayload,
    OptimizePayload,
    OrdersStagePayload,
    PolicyCheckPayload,
    RiskEvaluatePayload,
    TradeValidatePayload,
)
from warehouse.research.risk import evaluate_risk
from warehouse.research.risk.models import RiskHorizon, RiskRequest
from warehouse.research.risk.synthetic import rung

DEMO = DEMO_HOUSEHOLD_ID


def _msg(op: str, kind: Kind, payload) -> Message:
    return Message(op=op, kind=kind, payload=payload, correlation_id="c")


@pytest.fixture
def seeded() -> Iterator[None]:
    bootstrap_database(seed=True)
    yield


def test_ledger_positions_round_trip(seeded: None) -> None:
    with session_scope() as s:
        ctx = DispatchContext(session=s, actor_id="test")
        out = dispatch_message(
            ctx,
            _msg(
                "ledger.positions",
                Kind.QUERY,
                LedgerPositionsPayload(household_id=DEMO),
            ),
        )
        direct = list_lot_positions(s, household_id=DEMO)
    assert [p.lot_id for p in out.positions] == [p.lot_id for p in direct]


def test_risk_evaluate_round_trip(seeded: None) -> None:
    manifest = rung(1)
    request = RiskRequest(horizon=RiskHorizon.parse("5y"))
    with session_scope() as s:
        ctx = DispatchContext(session=s)
        out = dispatch_message(
            ctx,
            _msg(
                "risk.evaluate",
                Kind.EVALUATE,
                RiskEvaluatePayload(request=request, manifest=manifest),
            ),
        )
    assert out.model_dump() == evaluate_risk(request, manifest).model_dump()


def test_policy_check_round_trip(seeded: None) -> None:
    with session_scope() as s:
        positions = list_lot_positions(s, household_id=DEMO)
        ips = load_ips(s, DEMO)
        assert ips is not None
        ctx = DispatchContext(session=s)
        out = dispatch_message(
            ctx,
            _msg(
                "policy.check",
                Kind.EVALUATE,
                PolicyCheckPayload(
                    household_id=DEMO, positions=positions, ips=ips
                ),
            ),
        )
        direct = build_ips_drift_report_from_views(DEMO, positions, ips)
    assert out.model_dump() == direct.model_dump()


def test_optimizer_propose_round_trip(seeded: None) -> None:
    with session_scope() as s:
        positions = list_lot_positions(s, household_id=DEMO)
        ips = load_ips(s, DEMO)
        assert ips is not None
        ctx = DispatchContext(session=s)
        out = dispatch_message(
            ctx,
            _msg(
                "optimizer.propose",
                Kind.EVALUATE,
                OptimizePayload(
                    household_id=DEMO, positions=positions, ips=ips
                ),
            ),
        )
        direct = run_tax_aware_optimizer(DEMO, positions, ips)
    assert out.model_dump() == direct.model_dump()


def test_trade_validate_round_trip(seeded: None) -> None:
    with session_scope() as s:
        positions = list_lot_positions(s, household_id=DEMO)
        ips = load_ips(s, DEMO)
        assert ips is not None
        lot = positions[0]
        ctx = DispatchContext(session=s)
        out = dispatch_message(
            ctx,
            _msg(
                "trade.validate",
                Kind.EVALUATE,
                TradeValidatePayload(lot=lot, ips=ips),
            ),
        )
        allowed, binding = evaluate_lot_sell_allowed(lot, ips)
    assert (out.allowed, out.binding) == (allowed, binding)


class _Poison:
    """Raises on any attribute access — proves a handler never reads it."""

    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"EVALUATE handler touched session.{name}")


def test_evaluate_handlers_never_touch_session(seeded: None) -> None:
    with session_scope() as s:
        positions = list_lot_positions(s, household_id=DEMO)
        ips = load_ips(s, DEMO)
        assert ips is not None
    ctx = DispatchContext(session=_Poison())  # type: ignore[arg-type]
    request = RiskRequest(horizon=RiskHorizon.parse("5y"))
    cases = [
        _msg(
            "risk.evaluate",
            Kind.EVALUATE,
            RiskEvaluatePayload(request=request, manifest=rung(1)),
        ),
        _msg(
            "policy.check",
            Kind.EVALUATE,
            PolicyCheckPayload(
                household_id=DEMO, positions=positions, ips=ips
            ),
        ),
        _msg(
            "optimizer.propose",
            Kind.EVALUATE,
            OptimizePayload(household_id=DEMO, positions=positions, ips=ips),
        ),
        _msg(
            "trade.validate",
            Kind.EVALUATE,
            TradeValidatePayload(lot=positions[0], ips=ips),
        ),
    ]
    for msg in cases:
        dispatch_message(ctx, msg)  # must not raise


def test_ingest_run_command_via_dispatch(seeded: None) -> None:
    path = repo_root() / "tests/fixtures/fidelity_positions.csv"
    with session_scope() as s:
        ctx = DispatchContext(session=s, actor_id="test")
        out = dispatch_message(
            ctx,
            _msg(
                "ingest.run",
                Kind.COMMAND,
                IngestRunPayload(
                    household_id=DEMO,
                    custodian_id="custodian_fidelity",
                    path=str(path),
                ),
            ),
        )
    assert out.status == "success"
    assert out.rows_processed == 2


def test_orders_stage_gate_via_dispatch(seeded: None) -> None:
    """Gate invariant holds through dispatch — pending approval raises."""
    with session_scope() as s:
        run_and_persist_optimizer(s, DEMO)
        pending = next(
            a
            for a in list_approval_requests(s, household_id=DEMO)
            if a.status == ApprovalStatus.PENDING.value
        )
        ctx = DispatchContext(session=s, actor_id="test")
        with pytest.raises(ValueError, match="status is 'pending'"):
            dispatch_message(
                ctx,
                _msg(
                    "orders.stage",
                    Kind.COMMAND,
                    OrdersStagePayload(approval_request_id=pending.request_id),
                ),
            )
