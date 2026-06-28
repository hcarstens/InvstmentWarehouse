"""Phase 3 dashboard data — IPS drift, optimizer, approval, backtest."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from warehouse.dashboard.phase2_data import load_phase2_dashboard
from warehouse.dashboard.synthetic_ips_data import (
    SyntheticIpsDashboardData,
    load_synthetic_ips_matrix,
)
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.approval.service import (
    ApprovalRequestView,
    list_approval_requests,
)
from warehouse.decision.constraints import active_constraint_summary
from warehouse.decision.ips.monitor import (
    IpsDriftReport,
    build_ips_drift_report,
)
from warehouse.decision.ips.store import load_ips
from warehouse.decision.optimizer.runner import (
    OptimizationRunView,
    list_optimization_runs,
    run_and_persist_optimizer,
)
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.research.backtest.harness import (
    BacktestRunView,
    list_backtest_runs,
    run_backtest,
)


class Phase3DashboardData(BaseModel):
    household_id: str
    ips_drift: IpsDriftReport | None
    optimization_runs: list[OptimizationRunView]
    approval_requests: list[ApprovalRequestView]
    backtest_runs: list[BacktestRunView]
    active_constraints: list[str]
    synthetic_ips: SyntheticIpsDashboardData | None = None
    error: str | None = None


class ResearchBacktestData(BaseModel):
    household_id: str
    backtest_runs: list[BacktestRunView]
    error: str | None = None


def _ensure_demo_decision_runs() -> None:
    with session_scope() as session:
        if list_optimization_runs(session, DEMO_HOUSEHOLD_ID, limit=1):
            return
        run_and_persist_optimizer(session, DEMO_HOUSEHOLD_ID)
        if not list_backtest_runs(session, DEMO_HOUSEHOLD_ID, limit=1):
            run_backtest(
                session,
                DEMO_HOUSEHOLD_ID,
                start_date=date(2024, 1, 1),
                end_date=date(2026, 6, 24),
            )


def load_phase3_dashboard() -> Phase3DashboardData:
    try:
        bootstrap_database(seed=True)
        load_phase2_dashboard()
        _ensure_demo_decision_runs()
        with session_scope() as session:
            positions = list_lot_positions(
                session, household_id=DEMO_HOUSEHOLD_ID
            )
            ips = load_ips(session, DEMO_HOUSEHOLD_ID)
            drift = (
                build_ips_drift_report(
                    session, DEMO_HOUSEHOLD_ID, positions, ips
                )
                if ips
                else None
            )
            opts = list_optimization_runs(session, DEMO_HOUSEHOLD_ID)
            approvals = list_approval_requests(
                session, household_id=DEMO_HOUSEHOLD_ID
            )
            backtests = list_backtest_runs(session, DEMO_HOUSEHOLD_ID)
            constraints = active_constraint_summary(ips) if ips else []
        synthetic_ips = load_synthetic_ips_matrix()
        return Phase3DashboardData(
            household_id=DEMO_HOUSEHOLD_ID,
            ips_drift=drift,
            optimization_runs=opts,
            approval_requests=approvals,
            backtest_runs=backtests,
            active_constraints=constraints,
            synthetic_ips=synthetic_ips,
        )
    except Exception as err:
        return Phase3DashboardData(
            household_id=DEMO_HOUSEHOLD_ID,
            ips_drift=None,
            optimization_runs=[],
            approval_requests=[],
            backtest_runs=[],
            active_constraints=[],
            synthetic_ips=None,
            error=str(err),
        )


def load_research_backtest_data() -> ResearchBacktestData:
    try:
        bootstrap_database(seed=True)
        _ensure_demo_decision_runs()
        with session_scope() as session:
            backtests = list_backtest_runs(session, DEMO_HOUSEHOLD_ID)
        return ResearchBacktestData(
            household_id=DEMO_HOUSEHOLD_ID,
            backtest_runs=backtests,
        )
    except Exception as err:
        return ResearchBacktestData(
            household_id=DEMO_HOUSEHOLD_ID,
            backtest_runs=[],
            error=str(err),
        )
