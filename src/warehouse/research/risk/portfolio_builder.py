"""Build risk API portfolios from ledger positions and alternatives."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from warehouse.data.alternatives.service import AlternativeHoldingView
from warehouse.data.ledger.views import LotPositionView
from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    AssetPortfolio,
)

_TICKER_MAP: dict[str, tuple[AssetClass, int]] = {
    "VTI": (AssetClass.EQUITY, 1),
    "AAPL": (AssetClass.EQUITY, 1),
    "BND": (AssetClass.FIXED_INCOME, 1),
}

_DEFAULT_EQUITY = (AssetClass.EQUITY, 1)


def build_portfolio_from_holdings(
    household_id: str,
    positions: list[LotPositionView],
    alt_holdings: list[AlternativeHoldingView],
) -> AssetPortfolio:
    class_mv: dict[AssetClass, Decimal] = defaultdict(lambda: Decimal("0"))
    liquidity: dict[AssetClass, int] = {}

    for pos in positions:
        if pos.market_value is None or pos.market_value <= 0:
            continue
        asset_class, tier = _TICKER_MAP.get(pos.ticker or "", _DEFAULT_EQUITY)
        class_mv[asset_class] += pos.market_value
        liquidity[asset_class] = min(liquidity.get(asset_class, tier), tier)

    for alt in alt_holdings:
        if alt.current_nav <= 0:
            continue
        class_mv[AssetClass.ALTERNATIVES] += alt.current_nav
        liquidity[AssetClass.ALTERNATIVES] = 3

    total = sum(class_mv.values(), Decimal("0"))
    if total <= 0:
        raise ValueError("No markable household value for risk evaluation")

    allocations: list[AllocationSlot] = []
    for asset_class in sorted(class_mv, key=lambda ac: ac.value):
        weight = class_mv[asset_class] / total
        duration = None
        if asset_class == AssetClass.FIXED_INCOME:
            duration = Decimal("6.5")
        elif asset_class == AssetClass.ALTERNATIVES:
            duration = Decimal("7")
        allocations.append(
            AllocationSlot(
                asset_class=asset_class,
                weight=weight,
                duration_years=duration,
                liquidity_tier=liquidity.get(asset_class, 1),
            )
        )

    return AssetPortfolio(portfolio_id=household_id, allocations=allocations)
