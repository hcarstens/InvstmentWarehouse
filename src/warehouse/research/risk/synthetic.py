"""Synthetic portfolio manifests — rung ladder for regression (v0: 0–4)."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    AssetPortfolio,
    MeasurementMode,
)


def rung(level: int) -> AssetPortfolio:
    """Return a hand-built synthetic manifest at rung 0–4."""
    if level == 0:
        return AssetPortfolio(
            portfolio_id="synthetic-rung-0",
            source="synthetic",
            complexity=0,
            allocations=[
                AllocationSlot(
                    asset_class=AssetClass.EQUITY,
                    weight=Decimal("1"),
                    beta=Decimal("1"),
                    liquidity_tier=1,
                ),
            ],
        )
    if level == 1:
        return AssetPortfolio(
            portfolio_id="synthetic-rung-1",
            source="synthetic",
            complexity=1,
            allocations=[
                AllocationSlot(
                    asset_class=AssetClass.EQUITY,
                    weight=Decimal("0.6"),
                    beta=Decimal("1"),
                    liquidity_tier=1,
                ),
                AllocationSlot(
                    asset_class=AssetClass.FIXED_INCOME,
                    weight=Decimal("0.4"),
                    duration_years=Decimal("6.5"),
                    liquidity_tier=1,
                ),
            ],
        )
    if level == 2:
        return AssetPortfolio(
            portfolio_id="synthetic-rung-2",
            source="synthetic",
            complexity=2,
            allocations=[
                AllocationSlot(
                    asset_class=AssetClass.EQUITY,
                    weight=Decimal("0.5"),
                    beta=Decimal("1"),
                    liquidity_tier=1,
                ),
                AllocationSlot(
                    asset_class=AssetClass.FIXED_INCOME,
                    weight=Decimal("0.3"),
                    duration_years=Decimal("6.5"),
                    liquidity_tier=1,
                ),
                AllocationSlot(
                    asset_class=AssetClass.COMMODITIES,
                    weight=Decimal("0.1"),
                    liquidity_tier=2,
                ),
                AllocationSlot(
                    asset_class=AssetClass.FX,
                    weight=Decimal("0.1"),
                    liquidity_tier=1,
                ),
            ],
        )
    if level == 3:
        return AssetPortfolio(
            portfolio_id="synthetic-rung-3",
            source="synthetic",
            complexity=3,
            allocations=[
                AllocationSlot(
                    asset_class=AssetClass.EQUITY,
                    weight=Decimal("0.45"),
                    beta=Decimal("1"),
                    liquidity_tier=1,
                ),
                AllocationSlot(
                    asset_class=AssetClass.FIXED_INCOME,
                    weight=Decimal("0.25"),
                    duration_years=Decimal("6.5"),
                    liquidity_tier=1,
                ),
                AllocationSlot(
                    asset_class=AssetClass.COMMODITIES,
                    weight=Decimal("0.05"),
                    liquidity_tier=2,
                ),
                AllocationSlot(
                    asset_class=AssetClass.ALTERNATIVES,
                    weight=Decimal("0.15"),
                    duration_years=Decimal("7"),
                    liquidity_tier=3,
                    measurement=MeasurementMode.FERMI,
                    label="private_markets",
                ),
                AllocationSlot(
                    asset_class=AssetClass.CASH,
                    weight=Decimal("0.10"),
                    liquidity_tier=1,
                ),
            ],
        )
    if level == 4:
        return AssetPortfolio(
            portfolio_id="synthetic-rung-4",
            source="synthetic",
            complexity=4,
            allocations=[
                AllocationSlot(
                    asset_class=AssetClass.EQUITY,
                    weight=Decimal("0.70"),
                    beta=Decimal("1.2"),
                    liquidity_tier=1,
                    label="concentrated_equity",
                ),
                AllocationSlot(
                    asset_class=AssetClass.FIXED_INCOME,
                    weight=Decimal("0.15"),
                    duration_years=Decimal("5"),
                    liquidity_tier=1,
                ),
                AllocationSlot(
                    asset_class=AssetClass.ALTERNATIVES,
                    weight=Decimal("0.15"),
                    duration_years=Decimal("8"),
                    liquidity_tier=3,
                    measurement=MeasurementMode.FERMI,
                    label="concentrated_alts",
                ),
            ],
        )
    raise ValueError(f"synthetic rung {level} not defined (use 0..4)")
