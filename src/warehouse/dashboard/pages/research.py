"""Research plane dashboard page — warehouse.research panels."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse.dashboard.layout import wrap_page
from warehouse.dashboard.phase3_data import (
    ResearchBacktestData,
    load_research_backtest_data,
)
from warehouse.dashboard.render_phase3 import render_backtest_section
from warehouse.dashboard.render_risk import render_risk_section
from warehouse.dashboard.render_risk_build import render_risk_build_link_card
from warehouse.dashboard.risk_build_data import (
    RiskBuildReport,
    load_risk_build_report,
)
from warehouse.dashboard.risk_data import (
    RiskDashboardData,
    load_risk_dashboard,
)
from warehouse.dashboard.status import build_status_report
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID


class ResearchPageData(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    risk: RiskDashboardData
    backtests: ResearchBacktestData
    build: RiskBuildReport
    error: str | None = None


def load_research_page() -> ResearchPageData:
    risk = load_risk_dashboard(household_id=DEMO_HOUSEHOLD_ID)
    backtests = load_research_backtest_data()
    build = load_risk_build_report()
    error = risk.error or backtests.error
    return ResearchPageData(
        risk=risk,
        backtests=backtests,
        build=build,
        error=error,
    )


def render_research_page(data: ResearchPageData | None = None) -> str:
    bundle = data or load_research_page()
    report = build_status_report()
    body = "".join(
        [
            render_risk_build_link_card(bundle.build),
            render_risk_section(bundle.risk),
            render_backtest_section(
                bundle.backtests.backtest_runs,
                error=bundle.backtests.error,
            ),
        ]
    )
    subtitle = (
        f"Research plane · {report.version} · {report.app_env} · "
        f"<code>warehouse.research</code>"
    )
    return wrap_page(
        title="Investment Warehouse — Research",
        subtitle=subtitle,
        body=body,
        active_page_id="research",
        generated_at=bundle.generated_at,
        footer_extra='<a href="/api/pages/research">research API</a>',
    )
