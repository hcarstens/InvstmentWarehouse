"""rw0-rw1 report writer falsifiers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import warehouse.messaging.handlers  # noqa: F401 — registers catalog ops
from warehouse.data.security_master import AssetClass, TaxCharacter
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.ips.store import save_ips
from warehouse.infra.audit.store import list_audit_entries
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.models import (
    EntityRow,
    LotRow,
    MarketPriceRow,
    SecurityRow,
)
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging import (
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
)
from warehouse.messaging.core import REGISTRY
from warehouse.messaging.payloads import ReportBuildPayload
from warehouse.models.entities import EntityType
from warehouse.reporting.report_writer import (
    ReportAudience,
    ReportPeriod,
    ReportWriterError,
    build_and_write_household_reports,
    collect_report_bundle,
    render_markdown,
)

AS_OF = date(2026, 6, 24)
DEMO = DEMO_HOUSEHOLD_ID


@pytest.fixture
def seeded() -> Iterator[None]:
    bootstrap_database(seed=True)
    yield


def _msg(op: str, kind: Kind, payload) -> Message:
    return Message(op=op, kind=kind, payload=payload, correlation_id="c")


def _seed_household_with_lot(
    session,
    *,
    household_id: str,
    lot_id: str,
    security_id: str,
    account_id: str,
    qty: Decimal,
    cost: Decimal,
    price: Decimal,
    acq: date,
) -> None:
    session.add(
        EntityRow(
            entity_id=household_id,
            entity_type=EntityType.HOUSEHOLD,
            name="Report Writer HH",
            household_id=household_id,
        )
    )
    session.add(
        EntityRow(
            entity_id=account_id,
            entity_type=EntityType.ACCOUNT,
            name="Report Writer Account",
            household_id=household_id,
        )
    )
    session.add(
        SecurityRow(
            security_id=security_id,
            ticker=security_id.upper(),
            cusip=None,
            name=security_id,
            asset_class=AssetClass.EQUITY,
            tax_character=TaxCharacter.LTCG,
            liquidity_tier=1,
        )
    )
    session.add(
        LotRow(
            lot_id=lot_id,
            account_id=account_id,
            security_id=security_id,
            quantity=qty,
            cost_basis_per_share=cost,
            acquisition_date=acq,
        )
    )
    session.add(
        MarketPriceRow(
            security_id=security_id,
            price=price,
            as_of_date=AS_OF,
        )
    )
    session.flush()


def test_demo_household_bundle_has_performance_and_ips_drift() -> None:
    with session_scope() as session:
        bundle = collect_report_bundle(
            session,
            DEMO_HOUSEHOLD_ID,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    assert bundle.performance is not None
    assert bundle.ips_drift is not None
    assert bundle.performance.total_market_value > Decimal("0")
    assert bundle.ips_drift.household_id == DEMO_HOUSEHOLD_ID
    assert bundle.period.label == f"month-end-{AS_OF.isoformat()}"
    assert bundle.snapshot_id.startswith("rpt_")


def test_missing_ips_raises() -> None:
    hh = "hh_report_no_ips"
    with session_scope() as session:
        _seed_household_with_lot(
            session,
            household_id=hh,
            lot_id="lot_nips",
            security_id="sec_nips",
            account_id="acct_nips",
            qty=Decimal("1"),
            cost=Decimal("100"),
            price=Decimal("110"),
            acq=date(2024, 1, 1),
        )
        with pytest.raises(ReportWriterError, match="No IPS"):
            collect_report_bundle(
                session,
                hh,
                period=ReportPeriod.month_end(AS_OF),
                as_of=AS_OF,
            )


def test_missing_positions_raises() -> None:
    hh = "hh_report_no_positions"
    with session_scope() as session:
        session.add(
            EntityRow(
                entity_id=hh,
                entity_type=EntityType.HOUSEHOLD,
                name="No Positions",
                household_id=hh,
            )
        )
        save_ips(
            session,
            InvestmentPolicyStatement(
                ips_id="ips_npos",
                household_id=hh,
                version=1,
                effective_date="2026-01-01",
                allocation_targets=[
                    AllocationTarget(
                        asset_class=IpsSleeve.EQUITY,
                        min_weight=Decimal("0"),
                        max_weight=Decimal("1"),
                        target_weight=Decimal("1"),
                    ),
                ],
            ),
        )
        session.flush()
        with pytest.raises(ReportWriterError, match="No positions"):
            collect_report_bundle(
                session,
                hh,
                period=ReportPeriod.month_end(AS_OF),
                as_of=AS_OF,
            )


def test_limitations_include_tax_stub_when_zero() -> None:
    hh = "hh_report_zero_tax"
    with session_scope() as session:
        _seed_household_with_lot(
            session,
            household_id=hh,
            lot_id="lot_ztax",
            security_id="sec_ztax",
            account_id="acct_ztax",
            qty=Decimal("10"),
            cost=Decimal("100"),
            price=Decimal("100"),
            acq=date(2024, 1, 1),
        )
        save_ips(
            session,
            InvestmentPolicyStatement(
                ips_id="ips_ztax",
                household_id=hh,
                version=1,
                effective_date="2026-01-01",
                allocation_targets=[
                    AllocationTarget(
                        asset_class=IpsSleeve.EQUITY,
                        min_weight=Decimal("0"),
                        max_weight=Decimal("1"),
                        target_weight=Decimal("1"),
                    ),
                ],
            ),
        )
        session.flush()
        bundle = collect_report_bundle(
            session,
            hh,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    assert all(ts.tax_delta == Decimal("0") for ts in bundle.tax_scenarios)
    assert any("zero-stubbed" in note for note in bundle.limitations)


def test_external_markdown_has_bluf_and_exhibits(seeded: None) -> None:
    with session_scope() as session:
        bundle = collect_report_bundle(
            session,
            DEMO,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    md = render_markdown(bundle, ReportAudience.EXTERNAL)
    assert "## Executive summary (BLUF)" in md
    assert "Exhibit A" in md
    assert "## Execution & operations" not in md


def test_internal_markdown_has_execution_section(seeded: None) -> None:
    with session_scope() as session:
        bundle = collect_report_bundle(
            session,
            DEMO,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    md = render_markdown(bundle, ReportAudience.INTERNAL)
    assert "## Execution & operations" in md
    assert "firm-wide" in md


def test_report_build_registered_once() -> None:
    report_ops = [op for op in REGISTRY if op == "report.build"]
    assert len(report_ops) == 1


def test_report_build_is_command_kind() -> None:
    _, _, kind = REGISTRY["report.build"]
    assert kind is Kind.COMMAND


def test_report_build_writes_audit(seeded: None) -> None:
    with session_scope() as session:
        written = build_and_write_household_reports(
            session,
            DEMO,
            as_of_date=AS_OF,
            actor_id="test",
        )
        entries = list_audit_entries(session, household_id=DEMO)
    match = next(
        e
        for e in entries
        if e.action == "report_build" and e.resource_id == written.snapshot_id
    )
    assert match.details["snapshot_id"] == written.snapshot_id
    assert match.details["household_id"] == DEMO
    assert (
        match.details["internal_markdown_path"]
        == written.internal_markdown_path
    )


def test_report_build_writes_three_files(seeded: None) -> None:
    with session_scope() as session:
        written = build_and_write_household_reports(
            session,
            DEMO,
            as_of_date=AS_OF,
            actor_id="test",
        )
    assert Path(written.internal_markdown_path).is_file()
    assert Path(written.external_markdown_path).is_file()
    assert Path(written.bundle_json_path).is_file()
    assert written.period_label == f"month-end-{AS_OF.isoformat()}"
    assert Path(written.output_dir).name == written.snapshot_id


def test_report_build_messaging_round_trip(seeded: None) -> None:
    with session_scope() as session:
        ctx = DispatchContext(session=session, actor_id="test")
        via_msg = dispatch_message(
            ctx,
            _msg(
                "report.build",
                Kind.COMMAND,
                ReportBuildPayload(household_id=DEMO, as_of_date=AS_OF),
            ),
        )
        direct = build_and_write_household_reports(
            session,
            DEMO,
            as_of_date=AS_OF,
            actor_id="test",
        )
    assert via_msg.household_id == direct.household_id
    assert via_msg.period_label == direct.period_label
    assert via_msg.as_of_date == direct.as_of_date
    assert Path(via_msg.internal_markdown_path).is_file()
    assert Path(via_msg.external_markdown_path).is_file()
    assert Path(via_msg.bundle_json_path).is_file()


# --- rw3 month-end workflow falsifiers --------------------------------------


@pytest.fixture
def seeded_tmp_reports(tmp_path, monkeypatch) -> Iterator[Path]:
    bootstrap_database(seed=True)
    monkeypatch.setattr("warehouse.config.repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "warehouse.reporting.report_writer.writer.repo_root",
        lambda: tmp_path,
    )
    yield tmp_path


def test_run_month_end_reporting_writes_artifacts(
    seeded_tmp_reports: Path,
) -> None:
    from warehouse.workflows.month_end import run_month_end_reporting

    with session_scope() as session:
        written = run_month_end_reporting(
            session,
            DEMO,
            as_of_date=AS_OF,
            actor_id="test",
        )
    assert written.snapshot_id.startswith("rpt_")
    assert Path(written.internal_markdown_path).is_file()
    assert Path(written.external_markdown_path).is_file()
    assert Path(written.bundle_json_path).is_file()
    assert written.period_label == f"month-end-{AS_OF.isoformat()}"


def test_run_month_end_reporting_uses_report_build_audit(
    seeded_tmp_reports: Path,
) -> None:
    from warehouse.workflows.month_end import run_month_end_reporting

    with session_scope() as session:
        written = run_month_end_reporting(
            session,
            DEMO,
            as_of_date=AS_OF,
            actor_id="test",
        )
        entries = list_audit_entries(session, household_id=DEMO)
    match = next(
        e
        for e in entries
        if e.action == "report_build" and e.resource_id == written.snapshot_id
    )
    assert match.details["snapshot_id"] == written.snapshot_id
    assert match.details["household_id"] == DEMO


def test_month_end_batch_one_failure_does_not_swallow_others(
    seeded_tmp_reports: Path,
) -> None:
    from warehouse.workflows.month_end import run_month_end_reporting_batch

    bad_hh = "hh_month_end_no_ips"
    with session_scope() as session:
        session.add(
            EntityRow(
                entity_id=bad_hh,
                entity_type=EntityType.HOUSEHOLD,
                name="Month-end bad HH",
                household_id=bad_hh,
            )
        )
        session.flush()
        result = run_month_end_reporting_batch(
            session,
            as_of_date=AS_OF,
            household_ids=[DEMO, bad_hh],
            actor_id="test",
        )
    assert result.completed_count == 1
    assert result.failed_count == 1
    completed = next(o for o in result.outcomes if o.status == "completed")
    failed = next(o for o in result.outcomes if o.status == "failed")
    assert completed.household_id == DEMO
    assert completed.written is not None
    assert Path(completed.written.internal_markdown_path).is_file()
    assert failed.household_id == bad_hh
    assert failed.error is not None


def test_month_end_batch_failures_include_household_id(
    seeded_tmp_reports: Path,
) -> None:
    from warehouse.workflows.month_end import run_month_end_reporting_batch

    bad_hh = "hh_month_end_fail_ctx"
    with session_scope() as session:
        session.add(
            EntityRow(
                entity_id=bad_hh,
                entity_type=EntityType.HOUSEHOLD,
                name="Month-end fail HH",
                household_id=bad_hh,
            )
        )
        session.flush()
        result = run_month_end_reporting_batch(
            session,
            as_of_date=AS_OF,
            household_ids=[bad_hh],
            actor_id="test",
        )
    assert result.failed_count == 1
    outcome = result.outcomes[0]
    assert outcome.status == "failed"
    assert bad_hh in (outcome.error or "")


def test_month_end_reporting_raises_on_single_household_failure() -> None:
    from warehouse.workflows.month_end import run_month_end_reporting

    bad_hh = "hh_month_end_single_fail"
    bootstrap_database(seed=True)
    with session_scope() as session:
        session.add(
            EntityRow(
                entity_id=bad_hh,
                entity_type=EntityType.HOUSEHOLD,
                name="Single fail HH",
                household_id=bad_hh,
            )
        )
        session.flush()
        with pytest.raises(RuntimeError, match=bad_hh):
            run_month_end_reporting(
                session,
                bad_hh,
                as_of_date=AS_OF,
                actor_id="test",
            )
