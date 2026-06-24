"""Phase 3 — optimizer, IPS drift, approval, backtest."""

from datetime import date
from decimal import Decimal

import pytest

from warehouse.dashboard.phase3_data import load_phase3_dashboard
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.approval import ApprovalStatus
from warehouse.decision.approval.service import list_approval_requests, update_approval_status
from warehouse.decision.constraints import evaluate_lot_sell_allowed
from warehouse.decision.ips.monitor import build_ips_drift_report
from warehouse.decision.ips.store import load_ips
from warehouse.decision.optimizer.heuristics import run_tax_aware_optimizer
from warehouse.decision.optimizer.runner import run_and_persist_optimizer
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.schema_status import HEAD_REVISION
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.research.backtest import WalkForwardError
from warehouse.research.backtest.harness import run_backtest


def test_migration_phase3_head() -> None:
    from warehouse.infra.db.migrate import upgrade_head

    assert upgrade_head() == HEAD_REVISION


def test_ips_drift_report() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        positions = list_lot_positions(session, household_id=DEMO_HOUSEHOLD_ID)
        report = build_ips_drift_report(session, DEMO_HOUSEHOLD_ID, positions)
    assert report.household_id == DEMO_HOUSEHOLD_ID
    assert len(report.rows) == 2
    assert report.alerts


def test_restricted_lot_blocks_sell() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        positions = list_lot_positions(session, household_id=DEMO_HOUSEHOLD_ID)
        ips = load_ips(session, DEMO_HOUSEHOLD_ID)
        assert ips is not None
        aapl = next(p for p in positions if p.lot_id == "lot_aapl_1")
        allowed, binding = evaluate_lot_sell_allowed(aapl, ips)
    assert not allowed
    assert any("do_not_sell_lot" in b for b in binding)


def test_optimizer_harvests_loss_lot() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        positions = list_lot_positions(session, household_id=DEMO_HOUSEHOLD_ID)
        ips = load_ips(session, DEMO_HOUSEHOLD_ID)
        assert ips is not None
        result = run_tax_aware_optimizer(DEMO_HOUSEHOLD_ID, positions, ips)
    assert any(t.lot_id == "lot_vti_2" for t in result.trades)
    assert result.estimated_tax_delta < Decimal("0")


def test_optimizer_persist_and_approval() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        view = run_and_persist_optimizer(session, DEMO_HOUSEHOLD_ID)
        approvals = list_approval_requests(session, household_id=DEMO_HOUSEHOLD_ID)
    assert view.run_id.startswith("opt_")
    assert approvals
    matching = [a for a in approvals if a.optimization_run_id == view.run_id]
    assert len(matching) == 1
    assert matching[0].status == ApprovalStatus.PENDING.value


def test_approval_workflow() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        run_and_persist_optimizer(session, DEMO_HOUSEHOLD_ID)
        pending = list_approval_requests(session, household_id=DEMO_HOUSEHOLD_ID)[0]
        updated = update_approval_status(
            session,
            pending.request_id,
            status=ApprovalStatus.APPROVED,
            reviewer_id="advisor:test",
        )
    assert updated.status == ApprovalStatus.APPROVED.value
    assert updated.reviewer_id == "advisor:test"


def test_backtest_walk_forward_guard() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        with pytest.raises(WalkForwardError):
            run_backtest(
                session,
                DEMO_HOUSEHOLD_ID,
                start_date=date(2026, 6, 20),
                end_date=date(2026, 6, 24),
            )


def test_backtest_persist() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        result = run_backtest(
            session,
            DEMO_HOUSEHOLD_ID,
            start_date=date(2024, 1, 1),
            end_date=date(2026, 6, 24),
        )
    assert result.run_id.startswith("bt_")
    assert result.config_hash
    assert result.after_tax_return != Decimal("0")


def test_phase3_dashboard_loads() -> None:
    data = load_phase3_dashboard()
    assert data.error is None
    assert data.ips_drift is not None
    assert len(data.ips_drift.rows) == 2
    assert len(data.optimization_runs) >= 1
    assert len(data.approval_requests) >= 1
    assert len(data.backtest_runs) >= 1
    assert data.active_constraints
