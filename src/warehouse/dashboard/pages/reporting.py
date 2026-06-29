"""Reporting plane dashboard page — warehouse.reporting panels."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse.dashboard.layout import wrap_page
from warehouse.dashboard.phase4_data import (
    Phase4DashboardData,
    load_phase4_dashboard,
)
from warehouse.dashboard.render_phase4 import (
    render_performance_section,
    render_report_writer_section,
    render_tax_scenario_section,
)
from warehouse.dashboard.render_testing import render_qa_footnote
from warehouse.dashboard.report_writer_data import (
    ReportWriterPanelData,
    load_report_writer_panel,
)
from warehouse.dashboard.reporting_performance_data import (
    ReportingPerformanceData,
    load_reporting_performance,
)
from warehouse.dashboard.status import build_status_report


class ReportingPageData(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    phase4: Phase4DashboardData
    performance: ReportingPerformanceData
    report_writer: ReportWriterPanelData
    error: str | None = None


def load_reporting_page() -> ReportingPageData:
    phase4 = load_phase4_dashboard()
    performance = load_reporting_performance()
    report_writer = load_report_writer_panel()
    error = phase4.error or performance.error
    if report_writer.panel_status == "error":
        error = error or report_writer.error
    return ReportingPageData(
        phase4=phase4,
        performance=performance,
        report_writer=report_writer,
        error=error,
    )


def render_reporting_page(data: ReportingPageData | None = None) -> str:
    bundle = data or load_reporting_page()
    report = build_status_report()
    body = (
        render_performance_section(bundle.performance)
        + render_tax_scenario_section(bundle.phase4)
        + render_report_writer_section(bundle.report_writer)
    )
    subtitle = (
        f"Reporting plane · {report.version} · {report.app_env} · "
        f"<code>warehouse.reporting</code>"
    )
    return wrap_page(
        title="Investment Warehouse — Reporting",
        subtitle=subtitle,
        body=body,
        active_page_id="reporting",
        generated_at=bundle.generated_at,
        footer_extra=(
            f"{render_qa_footnote('reporting')} · "
            '<a href="/api/pages/reporting">reporting API</a>'
        ),
    )
