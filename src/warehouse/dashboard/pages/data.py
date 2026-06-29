"""Data plane dashboard page — warehouse.data panels."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse.dashboard.layout import wrap_page
from warehouse.dashboard.phase1_data import (
    Phase1DashboardData,
    load_phase1_dashboard,
)
from warehouse.dashboard.phase2_data import (
    Phase2DashboardData,
    load_phase2_dashboard,
)
from warehouse.dashboard.phase4_data import (
    Phase4DashboardData,
    load_phase4_dashboard,
)
from warehouse.dashboard.render_phase1 import render_phase1_sections
from warehouse.dashboard.render_phase2 import render_phase2_data_sections
from warehouse.dashboard.render_phase4 import render_phase4_data_sections
from warehouse.dashboard.render_testing import render_qa_footnote
from warehouse.dashboard.status import build_status_report


class DataPageData(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    phase1: Phase1DashboardData
    phase2: Phase2DashboardData
    phase4: Phase4DashboardData
    error: str | None = None


def load_data_page(
    *,
    security_query: str | None = None,
    custodian_id: str | None = None,
) -> DataPageData:
    phase1 = load_phase1_dashboard(security_query=security_query)
    phase2 = load_phase2_dashboard()
    phase4 = load_phase4_dashboard(custodian_id=custodian_id)
    error = phase1.error or phase2.error or phase4.error
    return DataPageData(
        phase1=phase1,
        phase2=phase2,
        phase4=phase4,
        error=error,
    )


def render_data_page(
    *,
    security_query: str | None = None,
    custodian_id: str | None = None,
    data: DataPageData | None = None,
) -> str:
    bundle = data or load_data_page(
        security_query=security_query,
        custodian_id=custodian_id,
    )
    report = build_status_report()
    body = "".join(
        [
            render_phase1_sections(bundle.phase1),
            render_phase2_data_sections(bundle.phase2),
            render_phase4_data_sections(bundle.phase4),
        ]
    )
    subtitle = (
        f"Data plane · {report.version} · {report.app_env} · "
        f"<code>warehouse.data</code>"
    )
    return wrap_page(
        title="Investment Warehouse — Data",
        subtitle=subtitle,
        body=body,
        active_page_id="data",
        generated_at=bundle.generated_at,
        footer_extra=(
            f"{render_qa_footnote('data')} · "
            '<a href="/api/pages/data">data API</a>'
        ),
    )
