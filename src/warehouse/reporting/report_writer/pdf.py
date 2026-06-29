"""Render external Markdown to PDF via Pandoc — render artifact only."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from importlib.resources import as_file, files
from pathlib import Path

from sqlalchemy.orm import Session

from warehouse.execution.reconciliation.service import (
    list_reconciliation_breaks,
)
from warehouse.reporting.report_writer.collect import ReportWriterError

_PANDOC_TIMEOUT_S = 120
_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_PDF_MAGIC = b"%PDF"
_PDF_ENGINES: tuple[str | None, ...] = (
    None,
    "wkhtmltopdf",
    "weasyprint",
    "xelatex",
    "pdflatex",
)


def external_pdf_delivery_blocked(session: Session) -> bool:
    """True when firm-wide open recon breaks block external PDF delivery."""
    return bool(list_reconciliation_breaks(session, open_only=True))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of file bytes."""
    return _sha256_bytes(path.read_bytes())


def _require_pandoc() -> str:
    path = shutil.which("pandoc")
    if path is None:
        raise ReportWriterError(
            "Pandoc is not installed — external PDF render unavailable. "
            "Install: brew install pandoc (macOS) or apt install pandoc "
            "(Linux). A PDF engine (e.g. wkhtmltopdf, basictex) may also "
            "be required."
        )
    return path


def _parse_front_matter(md_text: str) -> dict[str, str]:
    match = _FRONT_MATTER_RE.match(md_text)
    if not match:
        return {}
    block = match.group(1)
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def _css_path() -> Path | None:
    ref = files("warehouse.reporting.report_writer").joinpath("report_pdf.css")
    with as_file(ref) as path:
        return path if path.is_file() else None


def _pandoc_cmd(
    pandoc_bin: str,
    external_md_path: Path,
    output_pdf_path: Path,
    *,
    metadata: dict[str, str],
    pdf_engine: str | None,
) -> list[str]:
    cmd = [
        pandoc_bin,
        str(external_md_path),
        "-o",
        str(output_pdf_path),
        "--standalone",
        "--from",
        "markdown+yaml_metadata_block",
    ]
    css = _css_path()
    if css is not None:
        cmd.extend(["--css", str(css)])
    for key, value in metadata.items():
        cmd.extend(["-M", f"{key}={value}"])
    subtitle_parts = [
        metadata.get("audience", ""),
        metadata.get("classification", ""),
        f"period: {metadata.get('period', '')}",
        f"snapshot: {metadata.get('snapshot_id', '')}",
    ]
    subtitle = " | ".join(p for p in subtitle_parts if p)
    if subtitle:
        cmd.extend(["-M", f"subtitle={subtitle}"])
    if pdf_engine is not None:
        cmd.extend(["--pdf-engine", pdf_engine])
    return cmd


def _run_pandoc(cmd: list[str]) -> None:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_PANDOC_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired as err:
        raise ReportWriterError(
            f"Pandoc timed out after {_PANDOC_TIMEOUT_S}s"
        ) from err
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise ReportWriterError(
            f"Pandoc failed (exit {result.returncode}): {stderr or 'unknown'}"
        )


def render_external_pdf(
    external_md_path: Path,
    *,
    output_pdf_path: Path,
    snapshot_id: str,
) -> str:
    """Render external Markdown to PDF via Pandoc; return sha256 hex digest."""
    if not external_md_path.is_file():
        raise ReportWriterError(
            f"External Markdown missing: {external_md_path} "
            f"(snapshot_id={snapshot_id})"
        )
    md_text = external_md_path.read_text(encoding="utf-8")
    if not md_text.strip():
        raise ReportWriterError(
            f"External Markdown is empty: {external_md_path} "
            f"(snapshot_id={snapshot_id})"
        )

    pandoc_bin = _require_pandoc()
    metadata = _parse_front_matter(md_text)
    if metadata.get("snapshot_id") and metadata["snapshot_id"] != snapshot_id:
        raise ReportWriterError(
            f"Markdown snapshot_id {metadata['snapshot_id']!r} does not "
            f"match expected {snapshot_id!r}"
        )

    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for engine in _PDF_ENGINES:
        cmd = _pandoc_cmd(
            pandoc_bin,
            external_md_path,
            output_pdf_path,
            metadata=metadata,
            pdf_engine=engine,
        )
        try:
            _run_pandoc(cmd)
        except ReportWriterError as err:
            errors.append(str(err))
            continue
        if not output_pdf_path.is_file():
            errors.append("Pandoc produced no output file")
            continue
        pdf_bytes = output_pdf_path.read_bytes()
        if len(pdf_bytes) == 0:
            errors.append("Pandoc produced a zero-byte PDF")
            continue
        if not pdf_bytes.startswith(_PDF_MAGIC):
            errors.append("Pandoc output is not a valid PDF (missing %PDF)")
            continue
        digest = _sha256_bytes(pdf_bytes)
        if not digest:
            raise ReportWriterError("SHA-256 digest empty after PDF render")
        return digest

    detail = "; ".join(errors) if errors else "no PDF engine available"
    raise ReportWriterError(f"External PDF render failed: {detail}")
