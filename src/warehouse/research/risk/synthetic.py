"""Synthetic portfolio manifests — rung ladder for regression (v0: 0–4)."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    AssetPortfolio,
)


def rung(
    level: int,
    *,
    seed: int = 0,
    cohort_id: str | None = None,
) -> AssetPortfolio:
    """Return a synthetic manifest at rung 0–4.

    Rungs 0–2: hand-built sleeves (no DB).
    Rungs 3–4: compositional HNW generator (``warehouse.research.synthetic``).
    """
    if level in (3, 4):
        from warehouse.research.synthetic.cohort import default_cohort_for_rung
        from warehouse.research.synthetic.pipeline import emit_hnw_fixture

        cohort = cohort_id or default_cohort_for_rung(level)
        fixture = emit_hnw_fixture(cohort_id=cohort, seed=seed, rung=level)
        portfolio = fixture.asset_portfolio
        if portfolio is None:
            raise RuntimeError("HNW fixture missing Shape A projection")
        return portfolio

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
    raise ValueError(f"synthetic rung {level} not defined (use 0..4)")
