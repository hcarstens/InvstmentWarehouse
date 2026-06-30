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
        result = run_daily_refresh(
            session, custodian_file, household_id=DEMO_HOUSEHOLD_ID
        )
    assert result.status in {"success", "completed_with_breaks"}
    assert len(result.steps) == 5
    assert result.steps[0].step_name == "custodian_ingest"
    assert result.steps[0].status == "success"


def test_daily_refresh_reconciles_clean(custodian_file: Path) -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        result = run_daily_refresh(
            session, custodian_file, household_id=DEMO_HOUSEHOLD_ID
        )
    assert result.status == "success"


def test_reconcile_stale_as_of_date_opens_break(tmp_path: Path) -> None:
    from warehouse.data.ingest.runner import run_custodian_ingest
    from warehouse.execution.reconciliation.service import reconcile_ingest

    bootstrap_database(seed=True)
    stale = tmp_path / "stale_positions.csv"
    stale.write_text(
        "account_id,ticker,quantity,as_of_date\n"
        "acct_taxable,VTI,550,2024-01-01\n"
        "acct_taxable,AAPL,100,2024-01-01\n"
        "acct_ira,BND,300,2024-01-01\n"
    )
    with session_scope() as session:
        ingest = run_custodian_ingest(
            session,
            stale,
            household_id=DEMO_HOUSEHOLD_ID,
        )
        breaks = reconcile_ingest(
            session,
            ingest.run_id,
            household_id=DEMO_HOUSEHOLD_ID,
        )
    assert any("stale custodian file" in b.description for b in breaks)
    assert any(b.break_type.value == "stale_as_of" for b in breaks)


def test_recon_quantity_mismatch_opens_break(tmp_path: Path) -> None:
    from warehouse.data.ingest.runner import run_custodian_ingest
    from warehouse.execution.reconciliation.service import reconcile_ingest

    bootstrap_database(seed=True)
    wrong_qty = tmp_path / "wrong_qty.csv"
    wrong_qty.write_text(
        "account_id,ticker,quantity,as_of_date\n"
        "acct_taxable,VTI,500,2026-06-24\n"
        "acct_taxable,AAPL,100,2026-06-24\n"
        "acct_ira,BND,300,2026-06-24\n"
    )
    with session_scope() as session:
        ingest = run_custodian_ingest(
            session,
            wrong_qty,
            household_id=DEMO_HOUSEHOLD_ID,
        )
        breaks = reconcile_ingest(
            session,
            ingest.run_id,
            household_id=DEMO_HOUSEHOLD_ID,
        )
    qty_breaks = [
        b
        for b in breaks
        if "custodian=" in b.description and "ledger=" in b.description
    ]
    assert any("VTI" in b.description for b in qty_breaks)
    assert all(b.break_type.value == "quantity_mismatch" for b in qty_breaks)


def test_recon_ledger_only_position_opens_break(tmp_path: Path) -> None:
    from warehouse.data.ingest.runner import run_custodian_ingest
    from warehouse.execution.reconciliation.service import reconcile_ingest

    bootstrap_database(seed=True)
    missing_row = tmp_path / "missing_aapl.csv"
    missing_row.write_text(
        "account_id,ticker,quantity,as_of_date\n"
        "acct_taxable,VTI,550,2026-06-24\n"
        "acct_ira,BND,300,2026-06-24\n"
    )
    with session_scope() as session:
        ingest = run_custodian_ingest(
            session,
            missing_row,
            household_id=DEMO_HOUSEHOLD_ID,
        )
        breaks = reconcile_ingest(
            session,
            ingest.run_id,
            household_id=DEMO_HOUSEHOLD_ID,
        )
    assert any(
        "custodian=0" in b.description and "ledger=" in b.description
        for b in breaks
    )
    assert any(b.break_type.value == "ledger_only" for b in breaks)


def test_recon_mixed_as_of_date_opens_break(tmp_path: Path) -> None:
    from warehouse.data.ingest.runner import run_custodian_ingest
    from warehouse.execution.reconciliation.service import reconcile_ingest

    bootstrap_database(seed=True)
    mixed = tmp_path / "mixed_dates.csv"
    mixed.write_text(
        "account_id,ticker,quantity,as_of_date\n"
        "acct_taxable,VTI,550,2026-06-24\n"
        "acct_taxable,AAPL,100,2026-06-25\n"
        "acct_ira,BND,300,2026-06-24\n"
    )
    with session_scope() as session:
        ingest = run_custodian_ingest(
            session,
            mixed,
            household_id=DEMO_HOUSEHOLD_ID,
        )
        breaks = reconcile_ingest(
            session,
            ingest.run_id,
            household_id=DEMO_HOUSEHOLD_ID,
        )
    assert any("mixed as_of_date" in b.description for b in breaks)
    assert any(b.break_type.value == "mixed_as_of" for b in breaks)


def test_phase2_dashboard_loads() -> None:
    data = load_phase2_dashboard()
    assert data.error is None
    assert len(data.ingest_runs) >= 1
    assert len(data.positions) >= 4
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
