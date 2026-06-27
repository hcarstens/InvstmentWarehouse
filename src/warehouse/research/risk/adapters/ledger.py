"""Ledger adapter — build household risk manifests from DB positions."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from warehouse.config import repo_root
from warehouse.data.alternatives.service import (
    AlternativeHoldingView,
    list_alternative_holdings,
)
from warehouse.data.ingest.runner import list_ingest_runs
from warehouse.data.ledger.views import LotPositionView, list_lot_positions
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.research.risk.models import AssetPortfolio
from warehouse.research.risk.portfolio_builder import (
    build_portfolio_from_holdings,
)
from warehouse.workflows.daily_refresh import run_daily_refresh


class HouseholdRiskManifest(BaseModel):
    """Ledger-sourced manifest + household NAV for risk evaluation."""

    model_config = ConfigDict(frozen=True)

    portfolio: AssetPortfolio
    notional_usd: Decimal | None


def _ensure_demo_refresh() -> None:
    """Seed custodian ingest when demo DB has no ingest runs."""
    with session_scope() as session:
        if list_ingest_runs(session, limit=1):
            return
        run_daily_refresh(
            session,
            repo_root() / "tests/fixtures/schwab_positions.csv",
            household_id=DEMO_HOUSEHOLD_ID,
        )


def _household_notional(
    positions: list[LotPositionView],
    alt_holdings: list[AlternativeHoldingView],
) -> Decimal:
    lot_nav = sum(
        (p.market_value for p in positions if p.market_value is not None),
        Decimal("0"),
    )
    alt_nav = sum((a.current_nav for a in alt_holdings), Decimal("0"))
    return lot_nav + alt_nav


def build_household_manifest(
    household_id: str = DEMO_HOUSEHOLD_ID,
) -> HouseholdRiskManifest:
    """Project ledger lots + alts to sleeve-level ``AssetPortfolio``."""
    bootstrap_database(seed=True)
    _ensure_demo_refresh()
    with session_scope() as session:
        positions = list_lot_positions(session, household_id=household_id)
        alts = list_alternative_holdings(session, household_id=household_id)

    portfolio = build_portfolio_from_holdings(household_id, positions, alts)
    portfolio = portfolio.model_copy(update={"source": "ledger"})
    notional = _household_notional(positions, alts)
    return HouseholdRiskManifest(
        portfolio=portfolio,
        notional_usd=notional if notional > 0 else None,
    )
