"""Risk dashboard data — household portfolio manifest from ledger marks."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from warehouse.config import get_settings
from warehouse.dashboard.phase2_data import load_phase2_dashboard
from warehouse.data.alternatives.service import list_alternative_holdings
from warehouse.data.ledger.views import list_lot_positions
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.research.risk.engine import evaluate_portfolio_risk
from warehouse.research.risk.models import PortfolioRiskReport, RiskHorizon
from warehouse.research.risk.portfolio_builder import (
    build_portfolio_from_holdings,
)


class RiskDashboardData(BaseModel):
    household_id: str
    horizon_years: Decimal
    notional_usd: Decimal | None
    report: PortfolioRiskReport | None
    source: str
    error: str | None = None


def load_risk_dashboard(
    household_id: str = DEMO_HOUSEHOLD_ID,
    *,
    horizon_years: Decimal | None = None,
) -> RiskDashboardData:
    settings = get_settings()
    horizon = RiskHorizon.parse(
        horizon_years or settings.risk_dashboard_horizon_years)
    try:
        bootstrap_database(seed=True)
        load_phase2_dashboard()
        with session_scope() as session:
            positions = list_lot_positions(session, household_id=household_id)
            alts = list_alternative_holdings(
                session, household_id=household_id)
        portfolio = build_portfolio_from_holdings(
            household_id, positions, alts)
        notional = sum(
            (p.market_value for p in positions if p.market_value is not None),
            Decimal("0"),
        ) + sum((a.current_nav for a in alts), Decimal("0"))
        report = evaluate_portfolio_risk(
            portfolio,
            horizon,
            notional_usd=notional if notional > 0 else None,
        )
        return RiskDashboardData(
            household_id=household_id,
            horizon_years=horizon.years,
            notional_usd=notional if notional > 0 else None,
            report=report,
            source="positions_and_alternatives",
        )
    except Exception as err:
        return RiskDashboardData(
            household_id=household_id,
            horizon_years=horizon.years,
            notional_usd=None,
            report=None,
            source="positions_and_alternatives",
            error=str(err),
        )
