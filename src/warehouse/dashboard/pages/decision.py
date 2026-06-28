"""Decision plane dashboard page — warehouse.decision panels."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse.dashboard.advisory_data import (
    AdvisoryDashboardData,
    load_advisory_dashboard,
)
from warehouse.dashboard.analyst_data import (
    KillCriteriaWatchData,
    load_kill_criteria_dashboard,
)
from warehouse.dashboard.layout import wrap_page
from warehouse.dashboard.npa_data import NpaPanelData, load_npa_dashboard
from warehouse.dashboard.optimizer_data import (
    OptimizerPanelData,
    load_optimizer_dashboard,
)
from warehouse.dashboard.phase3_data import (
    Phase3DashboardData,
    load_phase3_dashboard,
)
from warehouse.dashboard.render_advisory import render_advisory_section
from warehouse.dashboard.render_analyst import (
    render_analyst_section,
    render_npa_section,
)
from warehouse.dashboard.render_phase3 import (
    render_optimizer_rebalance_section,
    render_phase3_decision_sections,
)
from warehouse.dashboard.status import build_status_report


class DecisionPageData(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    phase3: Phase3DashboardData
    optimizer: OptimizerPanelData
    advisory: AdvisoryDashboardData
    kill_criteria: KillCriteriaWatchData
    npa: NpaPanelData
    error: str | None = None


def load_decision_page() -> DecisionPageData:
    phase3 = load_phase3_dashboard()
    optimizer = load_optimizer_dashboard()
    advisory = load_advisory_dashboard(household_id=phase3.household_id)
    kill_criteria = load_kill_criteria_dashboard()
    npa = load_npa_dashboard()
    error = (
        phase3.error
        or optimizer.error
        or advisory.error
        or kill_criteria.error
        or npa.error
    )
    return DecisionPageData(
        phase3=phase3,
        optimizer=optimizer,
        advisory=advisory,
        kill_criteria=kill_criteria,
        npa=npa,
        error=error,
    )


def render_decision_page(data: DecisionPageData | None = None) -> str:
    bundle = data or load_decision_page()
    report = build_status_report()
    body = "".join(
        [
            render_phase3_decision_sections(bundle.phase3),
            render_optimizer_rebalance_section(bundle.optimizer),
            render_advisory_section(bundle.advisory),
            render_analyst_section(bundle.kill_criteria),
            render_npa_section(bundle.npa),
        ]
    )
    subtitle = (
        f"Decision plane · {report.version} · {report.app_env} · "
        f"<code>warehouse.decision</code>"
    )
    return wrap_page(
        title="Investment Warehouse — Decision",
        subtitle=subtitle,
        body=body,
        active_page_id="decision",
        generated_at=bundle.generated_at,
        footer_extra='<a href="/api/pages/decision">decision API</a>',
    )
