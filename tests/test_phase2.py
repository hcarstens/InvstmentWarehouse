"""Phase 2 — ingest, reconciliation, daily refresh, positions dashboard."""

from decimal import Decimal
from pathlib import Path

import pytest

from warehouse.config import repo_root
from warehouse.dashboard.phase2_data import load_phase2_dashboard
from warehouse.data.ingest.schwab_csv import parse_custodian_csv
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.schema_status import HEAD_REVISION
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.workflows.daily_refresh import run_daily_refresh


@pytest.fixture
def custodian_file() -> Path:
    return repo_root() / "tests/fixtures/schwab_positions.csv"


def test_migration_phase2_head() -> None:
    from warehouse.infra.db.migrate import upgrade_head

    assert upgrade_head() == HEAD_REVISION


def test_parse_custodian_csv(custodian_file: Path) -> None:
    records = parse_custodian_csv(custodian_file)
    assert len(records) == 3
    assert records[0].ticker == "VTI"


def test_daily_refresh_end_to_end(custodian_file: Path) -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        result = run_daily_refresh(session, custodian_file, household_id=DEMO_HOUSEHOLD_ID)
    assert result.status in {"success", "completed_with_breaks"}
    assert len(result.steps) == 5
    assert result.steps[0].step_name == "custodian_ingest"
    assert result.steps[0].status == "success"


def test_daily_refresh_reconciles_clean(custodian_file: Path) -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        result = run_daily_refresh(session, custodian_file, household_id=DEMO_HOUSEHOLD_ID)
    assert result.status == "success"


def test_phase2_dashboard_loads() -> None:
    data = load_phase2_dashboard()
    assert data.error is None
    assert len(data.ingest_runs) >= 1
    assert len(data.positions) == 3
    assert data.household_pnl is not None
    assert data.household_pnl.unrealized_gain > Decimal("0")
    assert len(data.refresh_steps) == 5
    assert len(data.audit_entries) >= 1


def test_research_sandbox_rejects_outside_path(tmp_path: Path) -> None:
    from warehouse.research.sandbox import resolve_research_path

    outside = tmp_path / "outside.csv"
    outside.write_text("x")
    with pytest.raises(ValueError, match="Research path must stay under"):
        resolve_research_path(outside)
