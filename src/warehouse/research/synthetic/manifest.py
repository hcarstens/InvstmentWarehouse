"""Project Shape B fixtures to Shape A ``AssetPortfolio``."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    AssetPortfolio,
    MeasurementMode,
)
from warehouse.research.synthetic.cohort import GENERATOR_VERSION
from warehouse.research.synthetic.models import HouseholdFixture, SyntheticLot

_TICKER_CLASS: dict[str, AssetClass] = {
    "VTI": AssetClass.EQUITY,
    "AAPL": AssetClass.EQUITY,
    "BND": AssetClass.FIXED_INCOME,
    "SYNPE": AssetClass.ALTERNATIVES,
}

_DEFAULT_EQUITY = AssetClass.EQUITY


def _lot_asset_class(lot: SyntheticLot) -> AssetClass:
    if lot.asset_class:
        return AssetClass(lot.asset_class)
    return _TICKER_CLASS.get(lot.ticker, _DEFAULT_EQUITY)


def _liquidity_tier(asset_class: AssetClass, *, fermi: bool) -> int:
    if fermi or asset_class == AssetClass.ALTERNATIVES:
        return 3
    if asset_class in (AssetClass.COMMODITIES, AssetClass.FX):
        return 2
    return 1


def project_to_asset_portfolio(fixture: HouseholdFixture) -> AssetPortfolio:
    """Aggregate lot marks + alt NAV into sleeve weights (HNW axiom: Σ lots = NAV)."""
    class_mv: dict[AssetClass, Decimal] = defaultdict(lambda: Decimal("0"))
    liquidity: dict[AssetClass, int] = {}
    fermi_classes: set[AssetClass] = set()

    for lot in fixture.lots:
        asset_class = _lot_asset_class(lot)
        market_value = lot.quantity * lot.market_price
        class_mv[asset_class] += market_value
        tier = _liquidity_tier(asset_class, fermi=False)
        liquidity[asset_class] = min(liquidity.get(asset_class, tier), tier)

    for alt in fixture.alternative_holdings:
        class_mv[AssetClass.ALTERNATIVES] += alt.current_nav
        liquidity[AssetClass.ALTERNATIVES] = 3
        fermi_classes.add(AssetClass.ALTERNATIVES)

    total = sum(class_mv.values(), Decimal("0"))
    if total <= 0:
        raise ValueError("fixture has no markable NAV for Shape A projection")

    allocations: list[AllocationSlot] = []
    for asset_class in sorted(class_mv, key=lambda ac: ac.value):
        weight = class_mv[asset_class] / total
        duration = None
        beta = None
        measurement = MeasurementMode.AUTO
        label = None
        if asset_class == AssetClass.FIXED_INCOME:
            duration = Decimal("6.5")
        elif asset_class == AssetClass.ALTERNATIVES:
            duration = Decimal("7")
            measurement = MeasurementMode.FERMI
            label = "private_markets"
        elif asset_class == AssetClass.EQUITY:
            beta = (
                Decimal("1.1")
                if fixture.provenance.rung >= 4
                else Decimal("1")
            )
        if asset_class in fermi_classes:
            measurement = MeasurementMode.FERMI

        allocations.append(
            AllocationSlot(
                asset_class=asset_class,
                weight=weight,
                duration_years=duration,
                beta=beta,
                liquidity_tier=liquidity.get(asset_class, 1),
                measurement=measurement,
                label=label,
            )
        )

    prov = fixture.provenance
    return AssetPortfolio(
        portfolio_id=fixture.household_id,
        allocations=allocations,
        source="synthetic",
        complexity=prov.rung,
        cohort_id=prov.cohort_id,
        generator_version=GENERATOR_VERSION,
        seed=prov.seed,
        tension_tags=list(prov.tension_tags),
    )
