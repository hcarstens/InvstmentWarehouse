"""Execution plane dashboard page — warehouse.execution panels."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse.dashboard.layout import wrap_page
from warehouse.dashboard.phase2_data import (
    Phase2DashboardData,
    load_phase2_dashboard,
)
from warehouse.dashboard.phase4_data import (
    Phase4DashboardData,
    load_phase4_dashboard,
)
from warehouse.dashboard.render_phase2 import render_phase2_execution_sections
from warehouse.dashboard.render_phase4 import render_phase4_execution_sections
from warehouse.dashboard.render_testing import render_qa_footnote
from warehouse.dashboard.status import build_status_report


class ExecutionPageData(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    phase2: Phase2DashboardData
    phase4: Phase4DashboardData
    error: str | None = None


def load_execution_page() -> ExecutionPageData:
    phase2 = load_phase2_dashboard()
    phase4 = load_phase4_dashboard()
    error = phase2.error or phase4.error
    return ExecutionPageData(
        phase2=phase2,
        phase4=phase4,
        error=error,
    )


def render_execution_page(data: ExecutionPageData | None = None) -> str:
    bundle = data or load_execution_page()
    report = build_status_report()
    body = "".join(
        [
            render_phase2_execution_sections(bundle.phase2),
            render_phase4_execution_sections(bundle.phase4),
        ]
    )
    subtitle = (
        f"Execution plane · {report.version} · {report.app_env} · "
        f"<code>warehouse.execution</code>"
    )
    return wrap_page(
        title="Investment Warehouse — Execution",
        subtitle=subtitle,
        body=body,
        active_page_id="execution",
        generated_at=bundle.generated_at,
        footer_extra=(
            f"{render_qa_footnote('execution')} · "
            '<a href="/api/pages/execution">execution API</a>'
        ),
    )
