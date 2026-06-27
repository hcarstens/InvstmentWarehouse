"""Project Shape B fixture lots to ``LotPositionView``.

Used for in-process workflow smokes (no DB session).
"""

from __future__ import annotations

from datetime import date

from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecurityAssetClass
from warehouse.research.risk.models import AssetClass as RiskAssetClass
from warehouse.research.synthetic.models import HouseholdFixture, SyntheticLot

_TICKER_SECURITY_CLASS: dict[str, SecurityAssetClass] = {
    "VTI": SecurityAssetClass.ETF,
    "BND": SecurityAssetClass.ETF,
    "AAPL": SecurityAssetClass.EQUITY,
    "DBC": SecurityAssetClass.ETF,
    "CASH": SecurityAssetClass.CASH,
}

_WASH_GROUPS: dict[str, str] = {
    "VTI": "us_equity_broad",
    "BND": "us_aggregate_bond",
    "AAPL": "aapl",
}


def _lot_liquidity_tier(lot: SyntheticLot) -> int:
    asset_class = RiskAssetClass(lot.asset_class)
    if asset_class == RiskAssetClass.ALTERNATIVES:
        return 3
    if asset_class in (RiskAssetClass.COMMODITIES, RiskAssetClass.FX):
        return 2
    return 1


_RISK_TO_SECURITY: dict[str, SecurityAssetClass] = {
    "equity": SecurityAssetClass.EQUITY,
    "fixed_income": SecurityAssetClass.FIXED_INCOME,
    "cash": SecurityAssetClass.CASH,
    "commodities": SecurityAssetClass.ETF,
    "alternatives": SecurityAssetClass.ALTERNATIVE,
}


def _security_asset_class(lot: SyntheticLot) -> SecurityAssetClass:
    if lot.ticker in _TICKER_SECURITY_CLASS:
        return _TICKER_SECURITY_CLASS[lot.ticker]
    return _RISK_TO_SECURITY.get(lot.asset_class, SecurityAssetClass.EQUITY)


def lot_positions_from_fixture(
    fixture: HouseholdFixture,
    *,
    restricted_tickers: frozenset[str] | None = None,
) -> list[LotPositionView]:
    """Map synthetic lots to ledger views — no DB session required."""
    accounts = {
        account.account_id: account.name for account in fixture.accounts
    }
    restricted = restricted_tickers or frozenset()
    positions: list[LotPositionView] = []
    for lot in fixture.lots:
        market_value = lot.quantity * lot.market_price
        total_cost = lot.quantity * lot.cost_basis_per_share
        unrealized = market_value - total_cost
        positions.append(
            LotPositionView(
                lot_id=lot.lot_id,
                account_id=lot.account_id,
                account_name=accounts.get(lot.account_id, lot.account_id),
                security_id=lot.ticker,
                ticker=lot.ticker,
                security_name=lot.ticker,
                security_asset_class=_security_asset_class(lot),
                liquidity_tier=_lot_liquidity_tier(lot),
                quantity=lot.quantity,
                cost_basis_per_share=lot.cost_basis_per_share,
                total_cost_basis=total_cost,
                market_price=lot.market_price,
                market_value=market_value,
                unrealized_gain=unrealized,
                acquisition_date=lot.acquisition_date,
                is_restricted=lot.ticker in restricted,
                wash_sale_substitute_group=_WASH_GROUPS.get(lot.ticker),
            )
        )
    return positions


def smoke_as_of_date(fixture: HouseholdFixture) -> date:
    """Fixed as-of for deterministic, walk-forward-safe workflow smokes."""
    _ = fixture
    return date(2026, 6, 27)
