"""Write report bundles to disk and audit the build."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.config import repo_root
from warehouse.infra.audit.store import write_audit
from warehouse.infra.db.models import MarketPriceRow
from warehouse.reporting.report_writer.collect import collect_report_bundle
from warehouse.reporting.report_writer.models import (
    ReportAudience,
    ReportBundle,
    ReportPeriod,
    WrittenHouseholdReport,
)
from warehouse.reporting.report_writer.render import render_markdown


def resolve_report_as_of(
    session: Session,
    as_of_date: date | None,
) -> date:
    """Default as-of: latest market marks, else today."""
    if as_of_date is not None:
        return as_of_date
    dates = session.scalars(select(MarketPriceRow.as_of_date)).all()
    return max(dates) if dates else date.today()


def _resolve_period(
    as_of: date,
    period_label: str | None,
) -> ReportPeriod:
    if period_label is not None:
        return ReportPeriod(label=period_label, end_date=as_of)
    return ReportPeriod.month_end(as_of)


def write_report_bundle(
    bundle: ReportBundle,
    *,
    output_dir: Path,
) -> WrittenHouseholdReport:
    """Render and persist internal/external Markdown plus bundle JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    internal_md_path = output_dir / "internal.md"
    external_md_path = output_dir / "external.md"
    bundle_path = output_dir / "bundle.json"

    internal_md_path.write_text(
        render_markdown(bundle, ReportAudience.INTERNAL),
        encoding="utf-8",
    )
    external_md_path.write_text(
        render_markdown(bundle, ReportAudience.EXTERNAL),
        encoding="utf-8",
    )
    bundle_path.write_text(
        bundle.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return WrittenHouseholdReport(
        snapshot_id=bundle.snapshot_id,
        household_id=bundle.household_id,
        period_label=bundle.period.label,
        as_of_date=bundle.as_of_date,
        generated_at=bundle.generated_at,
        output_dir=str(output_dir),
        internal_markdown_path=str(internal_md_path),
        external_markdown_path=str(external_md_path),
        bundle_json_path=str(bundle_path),
    )


def build_and_write_household_reports(
    session: Session,
    household_id: str,
    *,
    period_label: str | None = None,
    as_of_date: date | None = None,
    actor_id: str = "system:report_writer",
) -> WrittenHouseholdReport:
    """Collect bundle, render Markdown artifacts, and write audit row."""
    as_of = resolve_report_as_of(session, as_of_date)
    period = _resolve_period(as_of, period_label)
    bundle = collect_report_bundle(
        session,
        household_id,
        period=period,
        as_of=as_of,
    )
    output_dir = (
        repo_root()
        / "runs"
        / "reports"
        / household_id
        / period.label
        / bundle.snapshot_id
    )
    written = write_report_bundle(bundle, output_dir=output_dir)
    write_audit(
        session,
        actor_id=actor_id,
        action="report_build",
        resource_type="household_report",
        resource_id=bundle.snapshot_id,
        household_id=household_id,
        details={
            "snapshot_id": bundle.snapshot_id,
            "household_id": household_id,
            "output_dir": written.output_dir,
            "internal_markdown_path": written.internal_markdown_path,
            "external_markdown_path": written.external_markdown_path,
            "bundle_json_path": written.bundle_json_path,
            "period_label": period.label,
        },
    )
    session.flush()
    return written
