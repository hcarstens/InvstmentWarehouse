"""Infrastructure dashboard page — warehouse.infra panels."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse.dashboard.layout import wrap_page
from warehouse.dashboard.phase2_data import (
    Phase2DashboardData,
    load_phase2_dashboard,
)
from warehouse.dashboard.render_infra import (
    render_audit_log_section,
    render_infra_checks_section,
    render_planned_infra_panels,
)
from warehouse.dashboard.status import build_status_report
from warehouse.infra.health import InfraCheck, run_infra_checks


class InfraPageData(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    infra_checks: list[InfraCheck]
    phase2: Phase2DashboardData
    error: str | None = None


def load_infra_page() -> InfraPageData:
    phase2 = load_phase2_dashboard()
    infra_checks = run_infra_checks()
    error = phase2.error
    if any(c.status == "error" for c in infra_checks):
        infra_err = next(
            c.error or c.detail for c in infra_checks if c.status == "error"
        )
        error = error or infra_err
    return InfraPageData(
        infra_checks=infra_checks,
        phase2=phase2,
        error=error,
    )


def render_infra_page(data: InfraPageData | None = None) -> str:
    bundle = data or load_infra_page()
    report = build_status_report()
    body = "".join(
        [
            render_infra_checks_section(bundle.infra_checks),
            render_audit_log_section(bundle.phase2),
            render_planned_infra_panels(),
        ]
    )
    subtitle = (
        f"Infrastructure · {report.version} · {report.app_env} · "
        f"<code>warehouse.infra</code>"
    )
    return wrap_page(
        title="Investment Warehouse — Infra",
        subtitle=subtitle,
        body=body,
        active_page_id="infra",
        generated_at=bundle.generated_at,
        footer_extra='<a href="/api/pages/infra">infra API</a>',
    )
