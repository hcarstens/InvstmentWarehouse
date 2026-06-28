"""Phase 4 — OMS, multi-custodian, solver comparison, alts, tax scenarios."""

from decimal import Decimal
from pathlib import Path

import pytest

from warehouse.config import repo_root
from warehouse.dashboard.phase4_data import load_phase4_dashboard
from warehouse.data.ingest.fidelity_csv import parse_fidelity_csv
from warehouse.data.ingest.registry import get_parser
from warehouse.data.ingest.registry import (
    list_custodians as list_parser_custodians,
)
from warehouse.data.ingest.runner import run_custodian_ingest
from warehouse.decision.approval import ApprovalStatus
from warehouse.decision.approval.service import (
    list_approval_requests,
    update_approval_status,
)
from warehouse.decision.optimizer.compare import run_solver_comparison
from warehouse.decision.optimizer.runner import run_and_persist_optimizer
from warehouse.decision.tax.scenarios import (
    TaxScenarioOverlays,
    run_tax_scenario,
)
from warehouse.execution.oms import OrderStatus
from warehouse.execution.oms.service import (
    list_staged_orders,
    update_order_status,
)
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.schema_status import HEAD_REVISION
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID


@pytest.fixture
def fidelity_file() -> Path:
    return repo_root() / "tests/fixtures/fidelity_positions.csv"


def test_migration_phase4_head() -> None:
    from warehouse.infra.db.migrate import upgrade_head

    assert upgrade_head() == HEAD_REVISION


def test_fidelity_parser(fidelity_file: Path) -> None:
    records = parse_fidelity_csv(fidelity_file)
    assert len(records) == 2
    assert records[0].ticker == "VTI"


def test_ingest_registry() -> None:
    assert "custodian_schwab" in list_parser_custodians()
    assert "custodian_fidelity" in list_parser_custodians()
    parser = get_parser("custodian_fidelity")
    assert parser is not None


def test_fidelity_ingest(fidelity_file: Path) -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        summary = run_custodian_ingest(
            session,
            fidelity_file,
            custodian_id="custodian_fidelity",
            household_id=DEMO_HOUSEHOLD_ID,
        )
    assert summary.status == "success"
    assert summary.rows_processed == 2


def test_approval_decoupled_then_stage_dispatched() -> None:
    """Approval records only; staging is a separate dispatched op (§9.3)."""
    import warehouse.messaging.handlers  # noqa: F401 — register ops
    from warehouse.messaging import (
        DispatchContext,
        Kind,
        Message,
        dispatch_message,
    )
    from warehouse.messaging.payloads import OrdersStagePayload

    bootstrap_database(seed=True)
    with session_scope() as session:
        run_and_persist_optimizer(session, DEMO_HOUSEHOLD_ID)
        pending = [
            a
            for a in list_approval_requests(
                session, household_id=DEMO_HOUSEHOLD_ID
            )
            if a.status == ApprovalStatus.PENDING.value
        ]
        assert pending
        req_id = pending[0].request_id
        update_approval_status(
            session,
            req_id,
            status=ApprovalStatus.APPROVED,
            reviewer_id="advisor:test",
        )
        # Decoupled: approving alone does NOT stage.
        assert not [
            o
            for o in list_staged_orders(
                session, household_id=DEMO_HOUSEHOLD_ID
            )
            if o.approval_request_id == req_id
        ]
        # Chain orders.stage through dispatch.
        ctx = DispatchContext(session=session, actor_id="advisor:test")
        staged = dispatch_message(
            ctx,
            Message(
                op="orders.stage",
                kind=Kind.COMMAND,
                payload=OrdersStagePayload(approval_request_id=req_id),
                correlation_id="c",
            ),
        )
        orders = list_staged_orders(session, household_id=DEMO_HOUSEHOLD_ID)
    assert staged.orders
    assert orders[0].status == OrderStatus.STAGED.value
    assert orders[0].approval_request_id == req_id


def test_oms_gate_blocks_unapproved_staging() -> None:
    """OMS must refuse staging for PENDING approval — gate at boundary."""
    from warehouse.execution.oms.service import stage_orders_from_approval

    bootstrap_database(seed=True)
    with session_scope() as session:
        run_and_persist_optimizer(session, DEMO_HOUSEHOLD_ID)
        pending = [
            a
            for a in list_approval_requests(
                session, household_id=DEMO_HOUSEHOLD_ID
            )
            if a.status == ApprovalStatus.PENDING.value
        ][0]
        with pytest.raises(ValueError, match="status is 'pending'"):
            stage_orders_from_approval(session, pending.request_id)
        # No order for THIS pending approval should have leaked into staging.
        orders = list_staged_orders(session, household_id=DEMO_HOUSEHOLD_ID)
        assert not any(
            o.approval_request_id == pending.request_id for o in orders
        )


def test_order_state_machine() -> None:
    from warehouse.execution.oms.service import stage_orders_from_approval

    bootstrap_database(seed=True)
    with session_scope() as session:
        run_and_persist_optimizer(session, DEMO_HOUSEHOLD_ID)
        pending = [
            a
            for a in list_approval_requests(
                session, household_id=DEMO_HOUSEHOLD_ID
            )
            if a.status == ApprovalStatus.PENDING.value
        ][0]
        update_approval_status(
            session,
            pending.request_id,
            status=ApprovalStatus.APPROVED,
            reviewer_id="advisor:test",
        )
        # Decoupled: stage explicitly after approval.
        stage_orders_from_approval(
            session, pending.request_id, actor_id="advisor:test"
        )
        order = list_staged_orders(session, household_id=DEMO_HOUSEHOLD_ID)[0]
        submitted = update_order_status(
            session, order.order_id, status=OrderStatus.SUBMITTED
        )
        filled = update_order_status(
            session, order.order_id, status=OrderStatus.FILLED
        )
    assert submitted.status == OrderStatus.SUBMITTED.value
    assert filled.status == OrderStatus.FILLED.value


def test_solver_comparison() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        result = run_solver_comparison(session, DEMO_HOUSEHOLD_ID)
    assert result.comparison_id.startswith("cmp_")
    assert result.heuristic_runtime_ms >= 0
    assert result.mip_runtime_ms >= 0


def test_tax_scenario_niit() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        result = run_tax_scenario(
            session,
            DEMO_HOUSEHOLD_ID,
            scenario_name="test_niit",
            overlays=TaxScenarioOverlays(apply_niit=True),
        )
    assert result.tax_delta > Decimal("0")


def test_phase4_dashboard_loads() -> None:
    data = load_phase4_dashboard()
    assert data.error is None
    assert len(data.custodians) >= 2
    assert len(data.staged_orders) >= 1
    assert len(data.solver_comparisons) >= 1
    assert len(data.alternative_holdings) >= 1
    assert len(data.alternative_events) >= 1
    assert len(data.tax_scenarios) >= 1
    assert len(data.custodian_positions) >= 1
