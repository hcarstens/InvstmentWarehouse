"""Research plane dashboard page — warehouse.research panels."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse.dashboard.e2e_data import (
    E2ePanelData,
    load_e2e_smoke_dashboard,
)
from warehouse.dashboard.layout import wrap_page
from warehouse.dashboard.phase3_data import (
    ResearchBacktestData,
    load_research_backtest_data,
)
from warehouse.dashboard.render_e2e import render_e2e_smoke_section
from warehouse.dashboard.render_phase3 import render_backtest_section
from warehouse.dashboard.render_risk import render_risk_section
from warehouse.dashboard.render_risk_build import render_risk_build_link_card
from warehouse.dashboard.render_stats import render_daily_movements_section
from warehouse.dashboard.render_testing import render_qa_footnote
from warehouse.dashboard.risk_build_data import (
    RiskBuildReport,
    load_risk_build_report,
)
from warehouse.dashboard.risk_data import (
    RiskDashboardData,
    load_risk_dashboard,
)
from warehouse.dashboard.stats_data import (
    DailyMovementsData,
    load_daily_movements_dashboard,
)
from warehouse.dashboard.status import build_status_report
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID


class ResearchPageData(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    risk: RiskDashboardData
    backtests: ResearchBacktestData
    build: RiskBuildReport
    e2e: E2ePanelData
    daily_movements: DailyMovementsData
    error: str | None = None


def load_research_page() -> ResearchPageData:
    risk = load_risk_dashboard(household_id=DEMO_HOUSEHOLD_ID)
    backtests = load_research_backtest_data()
    build = load_risk_build_report()
    e2e = load_e2e_smoke_dashboard()
    daily_movements = load_daily_movements_dashboard()
    error = risk.error or backtests.error
    return ResearchPageData(
        risk=risk,
        backtests=backtests,
        build=build,
        e2e=e2e,
        daily_movements=daily_movements,
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
            render_daily_movements_section(bundle.daily_movements),
            render_e2e_smoke_section(bundle.e2e),
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
        footer_extra=(
            f"{render_qa_footnote('research')} · "
            '<a href="/api/pages/research">research API</a>'
        ),
    )
