"""rw0-rw4 report writer falsifiers."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

import warehouse.messaging.handlers  # noqa: F401 — registers catalog ops
from warehouse.data.security_master import AssetClass, TaxCharacter
from warehouse.decision.analyst import ACTIVE_RETURN_LABEL, AttributionError
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.ips.store import save_ips
from warehouse.infra.audit.store import list_audit_entries
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.models import (
    EntityRow,
    IngestRunRow,
    LotRow,
    MarketPriceRow,
    ReconciliationBreakRow,
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
    ReportBundle,
    ReportPeriod,
    ReportWriterError,
    approve_and_render_report,
    build_and_write_household_reports,
    collect_report_bundle,
    render_external_pdf,
    render_markdown,
)
from warehouse.reporting.report_writer.pdf import sha256_file

AS_OF = date(2026, 6, 24)
DEMO = DEMO_HOUSEHOLD_ID


def _resolve_open_breaks(session) -> None:
    """Clear firm-wide breaks so PDF render is not gated in unrelated tests."""
    now = datetime.now(UTC)
    for row in session.scalars(
        select(ReconciliationBreakRow).where(
            ReconciliationBreakRow.resolved.is_(False)
        )
    ).all():
        row.resolved = True
        row.resolved_at = now
    session.flush()


@pytest.fixture
def seeded() -> Iterator[None]:
    bootstrap_database(seed=True)
    with session_scope() as session:
        _resolve_open_breaks(session)
    yield


def _msg(op: str, kind: Kind, payload) -> Message:
    return Message(op=op, kind=kind, payload=payload, correlation_id="c")


def _build_then_approve(session, *, household_id: str = DEMO):
    """rw6: build a report, then advisor-approve it to render the PDF."""
    written = build_and_write_household_reports(
        session, household_id, as_of_date=AS_OF, actor_id="test"
    )
    return approve_and_render_report(
        session,
        household_id=household_id,
        snapshot_id=written.snapshot_id,
        reviewer_id="advisor:test",
    )


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
    suffix = uuid4().hex[:8]
    hh = f"hh_report_no_ips_{suffix}"
    with session_scope() as session:
        _seed_household_with_lot(
            session,
            household_id=hh,
            lot_id=f"lot_nips_{suffix}",
            security_id=f"sec_nips_{suffix}",
            account_id=f"acct_nips_{suffix}",
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
    suffix = uuid4().hex[:8]
    hh = f"hh_report_no_positions_{suffix}"
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
                ips_id=f"ips_npos_{suffix}",
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
    suffix = uuid4().hex[:8]
    hh = f"hh_report_zero_tax_{suffix}"
    with session_scope() as session:
        _seed_household_with_lot(
            session,
            household_id=hh,
            lot_id=f"lot_ztax_{suffix}",
            security_id=f"sec_ztax_{suffix}",
            account_id=f"acct_ztax_{suffix}",
            qty=Decimal("10"),
            cost=Decimal("100"),
            price=Decimal("100"),
            acq=date(2024, 1, 1),
        )
        save_ips(
            session,
            InvestmentPolicyStatement(
                ips_id=f"ips_ztax_{suffix}",
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
    # rw6: PDF is the client-of-record deliverable — not produced at build
    # time; it awaits advisor sign-off.
    assert written.external_pdf_path is None
    assert written.external_pdf_sha256 is None
    assert written.period_label == f"month-end-{AS_OF.isoformat()}"
    assert Path(written.output_dir).name == written.snapshot_id


def test_external_pdf_blocked_until_advisor_approves(seeded: None) -> None:
    with session_scope() as session:
        written = build_and_write_household_reports(
            session, DEMO, as_of_date=AS_OF, actor_id="test"
        )
        assert written.external_pdf_path is None  # awaiting approval
        approved = approve_and_render_report(
            session,
            household_id=DEMO,
            snapshot_id=written.snapshot_id,
            reviewer_id="advisor:test",
        )
    assert approved.external_pdf_path is not None
    assert Path(approved.external_pdf_path).is_file()
    assert approved.external_pdf_sha256 is not None


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
    with session_scope() as session:
        _resolve_open_breaks(session)
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

    bad_hh = f"hh_month_end_no_ips_{uuid4().hex[:8]}"
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

    bad_hh = f"hh_month_end_fail_ctx_{uuid4().hex[:8]}"
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

    bad_hh = f"hh_month_end_single_fail_{uuid4().hex[:8]}"
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


# --- rw4 PDF channel falsifiers ----------------------------------------------


@pytest.mark.pandoc
def test_report_build_writes_external_pdf_when_pandoc_available(
    seeded_tmp_reports: Path,
) -> None:
    if shutil.which("pandoc") is None:
        pytest.skip("pandoc not installed")

    with session_scope() as session:
        written = _build_then_approve(session)
    pdf_path = Path(written.external_pdf_path or "")
    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 0
    assert written.external_pdf_sha256 is not None


def test_external_pdf_sha256_matches_file_bytes(
    seeded_tmp_reports: Path,
) -> None:
    with session_scope() as session:
        written = _build_then_approve(session)
    pdf_path = Path(written.external_pdf_path or "")
    assert pdf_path.is_file()
    assert written.external_pdf_sha256 == sha256_file(pdf_path)


def test_pdf_render_raises_when_markdown_missing(tmp_path: Path) -> None:
    missing = tmp_path / "external.md"
    out = tmp_path / "external.pdf"
    with pytest.raises(ReportWriterError, match="missing"):
        render_external_pdf(
            missing,
            output_pdf_path=out,
            snapshot_id="rpt_missing",
        )
    assert not out.exists()


def test_pdf_render_raises_when_pandoc_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    md = tmp_path / "external.md"
    md.write_text(
        "---\ntitle: Test\nsnapshot_id: rpt_x\n---\n\n# Body\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "warehouse.reporting.report_writer.pdf.shutil.which",
        lambda _: None,
    )
    with pytest.raises(ReportWriterError, match="Pandoc is not installed"):
        render_external_pdf(
            md,
            output_pdf_path=tmp_path / "external.pdf",
            snapshot_id="rpt_x",
        )


def test_report_approved_audit_includes_pdf_hash(
    seeded_tmp_reports: Path,
) -> None:
    # rw6: the PDF hash lands on the report_approved row (advisor sign-off is
    # what produces the client-of-record PDF), not on report_build.
    with session_scope() as session:
        written = _build_then_approve(session)
        entries = list_audit_entries(session, household_id=DEMO)
    match = next(
        e
        for e in entries
        if e.action == "report_approved"
        and e.resource_id == written.snapshot_id
    )
    assert match.details["external_pdf_path"] == written.external_pdf_path
    assert match.details["external_pdf_sha256"] == written.external_pdf_sha256
    assert match.details["reviewer_id"] == "advisor:test"


def _seed_open_break(session, *, account_id: str = "acct_demo") -> None:
    ingest_id = f"ingest_rw4_{uuid4().hex[:8]}"
    break_id = f"break_rw4_{uuid4().hex[:8]}"
    session.add(
        IngestRunRow(
            run_id=ingest_id,
            custodian_id="custodian_fidelity",
            file_name="rw4_test.csv",
            status="completed",
            started_at=datetime(2026, 6, 24, tzinfo=UTC),
            finished_at=datetime(2026, 6, 24, tzinfo=UTC),
            rows_processed=1,
        )
    )
    session.add(
        ReconciliationBreakRow(
            break_id=break_id,
            ingest_run_id=ingest_id,
            account_id=account_id,
            security_id=None,
            description="rw4 gate test break",
            opened_at=datetime(2026, 6, 24, tzinfo=UTC),
            resolved=False,
        )
    )
    session.flush()


def test_external_pdf_blocked_when_open_breaks(
    seeded_tmp_reports: Path,
) -> None:
    with session_scope() as session:
        _seed_open_break(session)
        written = build_and_write_household_reports(
            session,
            DEMO,
            as_of_date=AS_OF,
            actor_id="test",
        )
        entries = list_audit_entries(session, household_id=DEMO)
    assert Path(written.external_markdown_path).is_file()
    assert written.external_pdf_path is None
    assert written.external_pdf_sha256 is None
    match = next(
        e
        for e in entries
        if e.action == "report_build" and e.resource_id == written.snapshot_id
    )
    assert match.details.get("external_pdf_blocked") == "true"
    assert match.details.get("reason") == "open_reconciliation_breaks"


def test_month_end_batch_awaits_approval(seeded_tmp_reports: Path) -> None:
    # rw6: month-end fan-out produces drafts; each PDF awaits per-household
    # advisor sign-off, so the batch itself delivers no PDFs.
    from warehouse.workflows.month_end import run_month_end_reporting_batch

    with session_scope() as session:
        result = run_month_end_reporting_batch(
            session,
            as_of_date=AS_OF,
            household_ids=[DEMO],
            actor_id="test",
        )
        completed = next(o for o in result.outcomes if o.status == "completed")
        assert completed.written is not None
        assert completed.written.external_pdf_path is None
        # Advisor approves → PDF becomes the deliverable.
        approved = approve_and_render_report(
            session,
            household_id=DEMO,
            snapshot_id=completed.written.snapshot_id,
            reviewer_id="advisor:test",
        )
    assert approved.external_pdf_path is not None
    assert approved.external_pdf_sha256 is not None
    assert Path(approved.external_pdf_path).is_file()


def test_pdf_render_subprocess_failure_propagates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    md = tmp_path / "external.md"
    md.write_text(
        "---\ntitle: Test\nsnapshot_id: rpt_sub\n---\n\n# Body\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "warehouse.reporting.report_writer.pdf.shutil.which",
        lambda _: "/usr/bin/pandoc",
    )

    def _fail(cmd, **kwargs):
        del kwargs
        proc = MagicMock()
        proc.returncode = 1
        proc.stderr = "engine missing"
        return proc

    monkeypatch.setattr(
        "warehouse.reporting.report_writer.pdf.subprocess.run",
        _fail,
    )
    with pytest.raises(ReportWriterError, match="External PDF render failed"):
        render_external_pdf(
            md,
            output_pdf_path=tmp_path / "external.pdf",
            snapshot_id="rpt_sub",
        )


def test_dashboard_panel_shows_pdf_hash(
    tmp_path,
    monkeypatch,
) -> None:
    from warehouse.dashboard.pages.reporting import render_reporting_page

    bootstrap_database(seed=True)
    with session_scope() as session:
        _resolve_open_breaks(session)
    monkeypatch.setattr("warehouse.config.repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "warehouse.reporting.report_writer.writer.repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "warehouse.dashboard.report_writer_data.reports_base",
        lambda: tmp_path,
    )
    with session_scope() as session:
        written = _build_then_approve(session)
    html = render_reporting_page()
    assert written.external_pdf_sha256 is not None
    assert written.external_pdf_sha256[:12] in html
    assert "Attribution exhibit:" in html
    assert "delivered" in html


# --- rw5 attribution + risk headline exhibits --------------------------------


def test_report_bundle_includes_attribution_on_demo_household(
    seeded: None,
) -> None:
    with session_scope() as session:
        bundle = collect_report_bundle(
            session,
            DEMO,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    assert bundle.attribution is not None
    assert len(bundle.attribution.positions) > 0


def test_attribution_exhibit_in_internal_markdown(seeded: None) -> None:
    with session_scope() as session:
        bundle = collect_report_bundle(
            session,
            DEMO,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    md = render_markdown(bundle, ReportAudience.INTERNAL)
    assert "## Exhibit D — Active return vs class assumption" in md
    assert ACTIVE_RETURN_LABEL in md
    exhibit_d = md.split("## Exhibit D")[1].split("## Exhibit E")[0]
    table_part = exhibit_d.split("**Attribution limitations:**")[0]
    lowered = table_part.lower()
    assert "alpha" not in lowered
    assert "idiosyncratic" not in lowered


def test_report_bundle_includes_risk_headline_on_demo_household(
    seeded: None,
) -> None:
    with session_scope() as session:
        bundle = collect_report_bundle(
            session,
            DEMO,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    assert bundle.risk_headline is not None
    l1 = bundle.risk_headline.report.level_1_portfolio
    assert l1.parametric_var is not None
    assert l1.parametric_es is not None


def test_risk_exhibit_shows_alpha_and_horizon(seeded: None) -> None:
    with session_scope() as session:
        bundle = collect_report_bundle(
            session,
            DEMO,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    md = render_markdown(bundle, ReportAudience.INTERNAL)
    assert "## Exhibit E — Risk headline" in md
    assert "α=" in md or "confidence" in md.lower()
    assert "h=" in md or "horizon" in md.lower()
    assert "mark_source=" in md


def test_external_markdown_omits_exhibits_d_and_e(seeded: None) -> None:
    with session_scope() as session:
        bundle = collect_report_bundle(
            session,
            DEMO,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    md = render_markdown(bundle, ReportAudience.EXTERNAL)
    assert "## Exhibit D" not in md
    assert "## Exhibit E" not in md


def test_attribution_limitations_in_bundle(seeded: None) -> None:
    with session_scope() as session:
        bundle = collect_report_bundle(
            session,
            DEMO,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    assert bundle.attribution is not None
    assert bundle.attribution.limitations
    assert any(
        lim in note
        for note in bundle.limitations
        for lim in bundle.attribution.limitations
    )


def test_collect_raises_on_attribution_failure(seeded: None) -> None:
    with patch(
        "warehouse.reporting.report_writer.collect.evaluate_attribution",
        side_effect=AttributionError("mapping failed"),
    ):
        with session_scope() as session:
            with pytest.raises(ReportWriterError, match=DEMO):
                collect_report_bundle(
                    session,
                    DEMO,
                    period=ReportPeriod.month_end(AS_OF),
                    as_of=AS_OF,
                )


def test_report_build_writes_attribution_to_bundle_json(
    seeded_tmp_reports: Path,
) -> None:
    with session_scope() as session:
        written = build_and_write_household_reports(
            session,
            DEMO,
            as_of_date=AS_OF,
            actor_id="test",
        )
    raw = Path(written.bundle_json_path).read_text(encoding="utf-8")
    bundle = ReportBundle.model_validate_json(raw)
    assert bundle.attribution is not None
    assert bundle.risk_headline is not None
    parsed = json.loads(raw)
    assert "attribution" in parsed
    assert "risk_headline" in parsed


def test_month_end_batch_inherits_attribution_fields(
    seeded_tmp_reports: Path,
) -> None:
    from warehouse.workflows.month_end import run_month_end_reporting_batch

    with session_scope() as session:
        result = run_month_end_reporting_batch(
            session,
            as_of_date=AS_OF,
            household_ids=[DEMO],
            actor_id="test",
        )
    completed = next(o for o in result.outcomes if o.status == "completed")
    assert completed.written is not None
    bundle = ReportBundle.model_validate_json(
        Path(completed.written.bundle_json_path).read_text(encoding="utf-8")
    )
    assert bundle.attribution is not None
    assert bundle.risk_headline is not None


def test_dashboard_panel_shows_attribution_status(
    tmp_path,
    monkeypatch,
) -> None:
    from warehouse.dashboard.pages.reporting import render_reporting_page

    bootstrap_database(seed=True)
    with session_scope() as session:
        _resolve_open_breaks(session)
    monkeypatch.setattr("warehouse.config.repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "warehouse.reporting.report_writer.writer.repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "warehouse.dashboard.report_writer_data.reports_base",
        lambda: tmp_path,
    )
    with session_scope() as session:
        build_and_write_household_reports(
            session,
            DEMO,
            as_of_date=AS_OF,
            actor_id="test",
        )
    html = render_reporting_page()
    assert "Attribution exhibit:" in html
    assert "Risk headline exhibit:" in html
    assert "live" in html
    assert "external.pdf" in html


# --- rw6 advisor approval gate falsifiers ------------------------------------


def test_approval_create_payload_requires_exactly_one_subject() -> None:
    from warehouse.messaging.payloads import ApprovalCreatePayload

    # neither subject
    with pytest.raises(ValueError, match="exactly one"):
        ApprovalCreatePayload(household_id=DEMO)
    # both subjects
    with pytest.raises(ValueError, match="exactly one"):
        ApprovalCreatePayload(
            household_id=DEMO,
            optimization_run_id="run_x",
            report_snapshot_id="rpt_x",
        )


def test_report_approval_round_trip_via_messaging(
    seeded_tmp_reports: Path,
) -> None:
    from warehouse.messaging.payloads import ApprovalCreatePayload

    with session_scope() as session:
        written = build_and_write_household_reports(
            session, DEMO, as_of_date=AS_OF, actor_id="test"
        )
        ctx = DispatchContext(session=session, actor_id="advisor:test")
        view = dispatch_message(
            ctx,
            _msg(
                "approval.create",
                Kind.COMMAND,
                ApprovalCreatePayload(
                    household_id=DEMO,
                    report_snapshot_id=written.snapshot_id,
                ),
            ),
        )
    assert view.subject_type == "report"
    assert view.subject_id == written.snapshot_id
    assert view.optimization_run_id is None
    assert view.status == "pending"


def test_recon_gate_precedes_approval_gate(seeded_tmp_reports: Path) -> None:
    # Even an approved report stays blocked while firm-wide breaks are open —
    # recon is the first gate (rw4), approval the second (rw6).
    with session_scope() as session:
        written = build_and_write_household_reports(
            session, DEMO, as_of_date=AS_OF, actor_id="test"
        )
        _seed_open_break(session)
        approved = approve_and_render_report(
            session,
            household_id=DEMO,
            snapshot_id=written.snapshot_id,
            reviewer_id="advisor:test",
        )
        entries = list_audit_entries(session, household_id=DEMO)
    assert approved.external_pdf_path is None
    match = next(
        e
        for e in entries
        if e.action == "report_approved"
        and e.resource_id == written.snapshot_id
    )
    assert match.details.get("reason") == "open_reconciliation_breaks"


def test_optimization_approval_keeps_run_id(seeded: None) -> None:
    # rw6 back-compat: optimization subjects still populate optimization_run_id
    # (OMS staging joins on it) with subject_type=optimization.
    from warehouse.decision.approval.service import create_approval_request

    with session_scope() as session:
        ctx_run = "run_rw6_backcompat"
        # No optimization_runs row exists, but SQLite FK enforcement is off by
        # default in this app; the create path itself is what we assert on.
        view = create_approval_request(session, ctx_run, DEMO)
    assert view.subject_type == "optimization"
    assert view.subject_id == ctx_run
    assert view.optimization_run_id == ctx_run


def test_dashboard_panel_awaiting_delivery_before_approval(
    tmp_path,
    monkeypatch,
) -> None:
    from warehouse.dashboard.report_writer_data import (
        load_report_writer_panel,
    )

    bootstrap_database(seed=True)
    with session_scope() as session:
        _resolve_open_breaks(session)
    monkeypatch.setattr("warehouse.config.repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "warehouse.reporting.report_writer.writer.repo_root",
        lambda: tmp_path,
    )
    with session_scope() as session:
        build_and_write_household_reports(
            session, DEMO, as_of_date=AS_OF, actor_id="test"
        )
    panel = load_report_writer_panel(
        household_id=DEMO, reports_base_path=tmp_path
    )
    assert panel.panel_status == "live"
    assert panel.delivery_state == "awaiting_delivery"
    assert panel.external_pdf_path is None
