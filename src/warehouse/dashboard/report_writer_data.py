"""Report writer panel data — artifact-backed (no report.build on HTTP)."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel

from warehouse.config import repo_root
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.reporting.report_writer.models import ReportBundle
from warehouse.reporting.report_writer.writer import household_reports_dir

_BLUF_HEADING = "## Executive summary (BLUF)"
_EMPTY_MSG = "No report artifacts — run warehouse report write or report.build"


class ReportWriterPanelData(BaseModel):
    household_id: str
    snapshot_id: str | None = None
    period_label: str | None = None
    as_of_date: date | None = None
    generated_at: datetime | None = None
    bluf_preview: str | None = None
    output_dir: str | None = None
    internal_markdown_path: str | None = None
    external_markdown_path: str | None = None
    bundle_json_path: str | None = None
    panel_status: str = "empty"  # empty | live | error
    error: str | None = None


def reports_base() -> Path:
    """Repo root for report artifact scans (monkeypatchable in tests)."""
    return repo_root()


def extract_bluf_preview(
    external_md: str,
    *,
    max_chars: int = 600,
) -> str:
    """Excerpt BLUF from external Markdown through the next ``##`` heading."""
    idx = external_md.find(_BLUF_HEADING)
    if idx == -1:
        return ""
    rest = external_md[idx + len(_BLUF_HEADING) :].lstrip("\n")
    next_match = re.search(r"\n## ", rest)
    body = rest[: next_match.start()] if next_match else rest
    body = body.strip()
    if len(body) <= max_chars:
        return body
    clipped = body[:max_chars]
    last_period = clipped.rfind(". ")
    if last_period > max_chars // 2:
        return clipped[: last_period + 1].strip()
    return clipped.rstrip() + "…"


def _bundle_sort_key(bundle_path: Path) -> datetime:
    try:
        bundle = ReportBundle.model_validate_json(
            bundle_path.read_text(encoding="utf-8")
        )
        key = bundle.generated_at
        if key.tzinfo is None:
            return key.replace(tzinfo=UTC)
        return key
    except (OSError, ValueError):
        mtime = bundle_path.parent.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=UTC)


def _latest_bundle_path(hh_dir: Path) -> Path | None:
    paths = list(hh_dir.glob("**/bundle.json"))
    if not paths:
        return None
    return max(paths, key=_bundle_sort_key)


def load_report_writer_panel(
    *,
    household_id: str = DEMO_HOUSEHOLD_ID,
    reports_base_path: Path | None = None,
) -> ReportWriterPanelData:
    """Load the latest written report artifacts for the dashboard panel."""
    base = (
        reports_base_path if reports_base_path is not None else reports_base()
    )
    hh_dir = household_reports_dir(household_id, base=base)
    bundle_path = _latest_bundle_path(hh_dir)
    if bundle_path is None:
        return ReportWriterPanelData(
            household_id=household_id,
            panel_status="empty",
            error=_EMPTY_MSG,
        )

    snapshot_dir = bundle_path.parent
    try:
        bundle = ReportBundle.model_validate_json(
            bundle_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as err:
        return ReportWriterPanelData(
            household_id=household_id,
            panel_status="error",
            error=str(err),
        )

    external_path = snapshot_dir / "external.md"
    if not external_path.is_file():
        return ReportWriterPanelData(
            household_id=household_id,
            snapshot_id=bundle.snapshot_id,
            panel_status="error",
            error=f"Missing external.md at {external_path}",
        )

    try:
        external_md = external_path.read_text(encoding="utf-8")
    except OSError as err:
        return ReportWriterPanelData(
            household_id=household_id,
            snapshot_id=bundle.snapshot_id,
            panel_status="error",
            error=str(err),
        )

    bluf = extract_bluf_preview(external_md)
    internal_path = snapshot_dir / "internal.md"
    internal_md = str(internal_path) if internal_path.is_file() else None
    return ReportWriterPanelData(
        household_id=household_id,
        snapshot_id=bundle.snapshot_id,
        period_label=bundle.period.label,
        as_of_date=bundle.as_of_date,
        generated_at=bundle.generated_at,
        bluf_preview=bluf or None,
        output_dir=str(snapshot_dir),
        internal_markdown_path=internal_md,
        external_markdown_path=str(external_path),
        bundle_json_path=str(bundle_path),
        panel_status="live",
    )
