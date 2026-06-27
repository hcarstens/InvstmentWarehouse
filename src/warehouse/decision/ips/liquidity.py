"""Liquidity tier rollup for IPS floor checks."""

from __future__ import annotations

from decimal import Decimal

from warehouse.data.ledger.views import LotPositionView


def liquid_tier_nav_share(
    positions: list[LotPositionView],
    *,
    max_tier: int = 2,
) -> Decimal:
    """Share of NAV in positions at liquidity tier ``max_tier`` or better."""
    total_mv = Decimal("0")
    liquid_mv = Decimal("0")
    for pos in positions:
        if pos.market_value is None:
            continue
        total_mv += pos.market_value
        if pos.liquidity_tier <= max_tier:
            liquid_mv += pos.market_value
    if total_mv <= 0:
        return Decimal("0")
    return liquid_mv / total_mv
