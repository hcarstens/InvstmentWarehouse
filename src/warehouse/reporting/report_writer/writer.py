"""Write report bundles to disk and audit the build."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.config import repo_root
from warehouse.infra.audit.store import write_audit
from warehouse.infra.db.models import MarketPriceRow
from warehouse.reporting.report_writer.collect import (
    ReportWriterError,
    collect_report_bundle,
)
from warehouse.reporting.report_writer.models import (
    ReportAudience,
    ReportBundle,
    ReportPeriod,
    WrittenHouseholdReport,
)
from warehouse.reporting.report_writer.pdf import (
    external_pdf_delivery_blocked,
    render_external_pdf,
    sha256_file,
)
from warehouse.reporting.report_writer.render import render_markdown


def household_reports_dir(
    household_id: str,
    *,
    base: Path | None = None,
) -> Path:
    """Path to ``runs/reports/{household_id}`` under *base* or repo root."""
    root = base if base is not None else repo_root()
    return root / "runs" / "reports" / household_id


def find_latest_written_report(
    household_id: str,
    *,
    base: Path | None = None,
) -> WrittenHouseholdReport | None:
    """Return the most recently generated report for a household, if any."""
    hh_dir = household_reports_dir(household_id, base=base)
    if not hh_dir.is_dir():
        return None

    best: tuple[datetime, WrittenHouseholdReport] | None = None
    for bundle_path in hh_dir.glob("**/bundle.json"):
        snapshot_dir = bundle_path.parent
        try:
            bundle = ReportBundle.model_validate_json(
                bundle_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue
        sort_key = bundle.generated_at
        if sort_key.tzinfo is None:
            sort_key = sort_key.replace(tzinfo=UTC)
        pdf_path = snapshot_dir / "external.pdf"
        pdf_sha: str | None = None
        if pdf_path.is_file():
            try:
                pdf_sha = sha256_file(pdf_path)
            except OSError:
                pdf_sha = None
        written = WrittenHouseholdReport(
            snapshot_id=bundle.snapshot_id,
            household_id=bundle.household_id,
            period_label=bundle.period.label,
            as_of_date=bundle.as_of_date,
            generated_at=bundle.generated_at,
            output_dir=str(snapshot_dir),
            internal_markdown_path=str(snapshot_dir / "internal.md"),
            external_markdown_path=str(snapshot_dir / "external.md"),
            bundle_json_path=str(bundle_path),
            external_pdf_path=str(pdf_path) if pdf_path.is_file() else None,
            external_pdf_sha256=pdf_sha,
        )
        if best is None or sort_key > best[0]:
            best = (sort_key, written)
    return best[1] if best else None


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


def _attach_external_pdf(
    session: Session,
    *,
    bundle: ReportBundle,
    written: WrittenHouseholdReport,
    household_id: str,
    as_of: date,
) -> tuple[WrittenHouseholdReport, dict[str, str]]:
    """Render external PDF when recon allows; return audit detail extras."""
    # ADVISOR REVIEW GATE (human) ──► client delivery (external PDF)
    # Full document-approval workflow deferred — needs approval.create for
    # documents (today tied to optimization_run_id). See plan §10.
    extra: dict[str, str] = {}
    if external_pdf_delivery_blocked(session):
        extra["external_pdf_blocked"] = "true"
        extra["reason"] = "open_reconciliation_breaks"
        return written, extra

    pdf_path = Path(written.output_dir) / "external.pdf"
    try:
        digest = render_external_pdf(
            Path(written.external_markdown_path),
            output_pdf_path=pdf_path,
            snapshot_id=bundle.snapshot_id,
        )
    except ReportWriterError as err:
        raise ReportWriterError(
            f"External PDF render failed for household_id={household_id} "
            f"snapshot_id={bundle.snapshot_id} as_of={as_of.isoformat()}: "
            f"{err}"
        ) from err

    on_disk = sha256_file(pdf_path)
    if on_disk != digest:
        raise ReportWriterError(
            f"PDF hash mismatch for household_id={household_id} "
            f"snapshot_id={bundle.snapshot_id}: render={digest}, "
            f"disk={on_disk}"
        )

    updated = written.model_copy(
        update={
            "external_pdf_path": str(pdf_path),
            "external_pdf_sha256": digest,
        }
    )
    extra["external_pdf_path"] = str(pdf_path)
    extra["external_pdf_sha256"] = digest
    return updated, extra


def build_and_write_household_reports(
    session: Session,
    household_id: str,
    *,
    period_label: str | None = None,
    as_of_date: date | None = None,
    actor_id: str = "system:report_writer",
) -> WrittenHouseholdReport:
    """Collect bundle, render Markdown artifacts, PDF, and write audit row."""
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
    written, pdf_extra = _attach_external_pdf(
        session,
        bundle=bundle,
        written=written,
        household_id=household_id,
        as_of=as_of,
    )
    audit_details: dict[str, str] = {
        "snapshot_id": bundle.snapshot_id,
        "household_id": household_id,
        "output_dir": written.output_dir,
        "internal_markdown_path": written.internal_markdown_path,
        "external_markdown_path": written.external_markdown_path,
        "bundle_json_path": written.bundle_json_path,
        "period_label": period.label,
    }
    audit_details.update(pdf_extra)
    write_audit(
        session,
        actor_id=actor_id,
        action="report_build",
        resource_type="household_report",
        resource_id=bundle.snapshot_id,
        household_id=household_id,
        details=audit_details,
    )
    session.flush()
    return written
