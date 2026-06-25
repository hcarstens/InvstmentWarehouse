"""Liquidity-time risk units — days to liquidate at 10% ADV."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.assumptions import LIQUIDITY_DAYS_BY_TIER
from warehouse.research.risk.models import (
    AllocationSlot,
    LiquidityRisk,
    LiquidityTierRisk,
    RiskMetric,
    RiskUnitType,
)


def evaluate_liquidity(slots: list[AllocationSlot]) -> LiquidityRisk:
    tier_weights: dict[int, Decimal] = {}
    for slot in slots:
        prior = tier_weights.get(slot.liquidity_tier, Decimal("0"))
        tier_weights[slot.liquidity_tier] = prior + slot.weight

    by_tier: list[LiquidityTierRisk] = []
    weighted_days = Decimal("0")
    for tier in sorted(tier_weights):
        weight = tier_weights[tier]
        days = LIQUIDITY_DAYS_BY_TIER[tier]
        weighted_days += weight * days
        by_tier.append(
            LiquidityTierRisk(
                tier=tier,
                weight=weight,
                days_to_liquidate=RiskMetric(
                    value=days,
                    unit_type=RiskUnitType.LIQUIDITY_DAYS,
                    method="tier_prior",
                    mark_source="model_prior",
                    approximation="days_at_10pct_adv",
                ),
            )
        )

    return LiquidityRisk(
        weighted_days=RiskMetric(
            value=weighted_days,
            unit_type=RiskUnitType.LIQUIDITY_DAYS,
            method="weight_weighted_tier_prior",
            mark_source="model_prior",
            approximation="portfolio_weighted_liquidity_days",
        ),
        by_tier=by_tier,
    )
