"""Phase 2 dashboard data — ingest, positions, reconciliation, audit."""

from pydantic import BaseModel

from warehouse.config import repo_root
from warehouse.data.ingest.runner import IngestRunSummary, list_ingest_runs
from warehouse.data.ledger.views import (
    HouseholdPnlSummary,
    LotPositionView,
    household_pnl_summary,
)
from warehouse.data.ledger.views import (
    list_lot_positions as load_lot_positions,
)
from warehouse.execution.reconciliation.service import (
    ReconciliationBreak,
    list_reconciliation_breaks,
)
from warehouse.infra.audit import AuditEntry
from warehouse.infra.audit.store import list_audit_entries
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.workflows.daily_refresh import (
    RefreshStepView,
    latest_refresh_steps,
    run_daily_refresh,
)


class Phase2DashboardData(BaseModel):
    household_id: str
    ingest_runs: list[IngestRunSummary]
    positions: list[LotPositionView]
    household_pnl: HouseholdPnlSummary | None
    reconciliation_breaks: list[ReconciliationBreak]
    refresh_steps: list[RefreshStepView]
    audit_entries: list[AuditEntry]
    error: str | None = None


def _demo_custodian_file() -> str:
    return str(repo_root() / "tests/fixtures/schwab_positions.csv")


def _ensure_demo_refresh() -> None:
    with session_scope() as session:
        if list_ingest_runs(session, limit=1):
            return
        run_daily_refresh(
            session,
            repo_root() / "tests/fixtures/schwab_positions.csv",
            household_id=DEMO_HOUSEHOLD_ID,
        )


def load_phase2_dashboard() -> Phase2DashboardData:
    try:
        bootstrap_database(seed=True)
        _ensure_demo_refresh()
        with session_scope() as session:
            ingest_runs = list_ingest_runs(session)
            positions = load_lot_positions(
                session, household_id=DEMO_HOUSEHOLD_ID
            )
            pnl = household_pnl_summary(session, DEMO_HOUSEHOLD_ID)
            breaks = list_reconciliation_breaks(session, open_only=True)
            steps = latest_refresh_steps(session, DEMO_HOUSEHOLD_ID)
            audit = list_audit_entries(session, household_id=DEMO_HOUSEHOLD_ID)
        return Phase2DashboardData(
            household_id=DEMO_HOUSEHOLD_ID,
            ingest_runs=ingest_runs,
            positions=positions,
            household_pnl=pnl,
            reconciliation_breaks=breaks,
            refresh_steps=steps,
            audit_entries=audit,
        )
    except Exception as err:
        return Phase2DashboardData(
            household_id=DEMO_HOUSEHOLD_ID,
            ingest_runs=[],
            positions=[],
            household_pnl=None,
            reconciliation_breaks=[],
            refresh_steps=[],
            audit_entries=[],
            error=str(err),
        )
