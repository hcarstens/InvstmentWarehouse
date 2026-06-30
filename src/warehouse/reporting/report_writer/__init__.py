"""Report writer — compile frozen facts into household report packs.

Import is **lazy** (PEP 562). A bare
``import warehouse.reporting.report_writer`` pulls only this facade — none of
the five planes the compiler depends on (rw8). Each exported name resolves to
its submodule on first attribute access, so ``from
warehouse.reporting.report_writer import collect_report_bundle`` still works
while the bare package import stays plane-free.

Every production consumer (cli, dashboard, messaging.handlers, workflows)
already imports the submodules directly; this facade is import-convenience only
and must not eagerly load them — eager re-export is what made *any* importer of
the package pull the whole plane fan-out and amplified the ``daily_refresh``
import cycle (Lib6 single entry point, Cartography clean boundaries).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from warehouse.reporting.report_writer.collect import (
        ReportWriterError as ReportWriterError,
    )
    from warehouse.reporting.report_writer.collect import (
        collect_report_bundle as collect_report_bundle,
    )
    from warehouse.reporting.report_writer.models import (
        ReportAudience as ReportAudience,
    )
    from warehouse.reporting.report_writer.models import (
        ReportBundle as ReportBundle,
    )
    from warehouse.reporting.report_writer.models import (
        ReportPeriod as ReportPeriod,
    )
    from warehouse.reporting.report_writer.models import (
        WrittenHouseholdReport as WrittenHouseholdReport,
    )
    from warehouse.reporting.report_writer.pdf import (
        external_pdf_delivery_blocked as external_pdf_delivery_blocked,
    )
    from warehouse.reporting.report_writer.pdf import (
        render_external_pdf as render_external_pdf,
    )
    from warehouse.reporting.report_writer.pdf import (
        sha256_file as sha256_file,
    )
    from warehouse.reporting.report_writer.render import (
        render_markdown as render_markdown,
    )
    from warehouse.reporting.report_writer.writer import (
        approve_and_render_report as approve_and_render_report,
    )
    from warehouse.reporting.report_writer.writer import (
        build_and_write_household_reports as build_and_write_household_reports,
    )
    from warehouse.reporting.report_writer.writer import (
        find_latest_written_report as find_latest_written_report,
    )
    from warehouse.reporting.report_writer.writer import (
        write_report_bundle as write_report_bundle,
    )

_EXPORTS: dict[str, str] = {
    "ReportWriterError": "collect",
    "collect_report_bundle": "collect",
    "ReportAudience": "models",
    "ReportBundle": "models",
    "ReportPeriod": "models",
    "WrittenHouseholdReport": "models",
    "external_pdf_delivery_blocked": "pdf",
    "render_external_pdf": "pdf",
    "sha256_file": "pdf",
    "render_markdown": "render",
    "approve_and_render_report": "writer",
    "build_and_write_household_reports": "writer",
    "find_latest_written_report": "writer",
    "write_report_bundle": "writer",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> object:
    submodule = _EXPORTS.get(name)
    if submodule is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f"{__name__}.{submodule}")
    return getattr(module, name)


def __dir__() -> list[str]:
    return list(__all__)
