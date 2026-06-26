"""Level 4 named historical stress replay."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.assumptions import RiskAssumptions
from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    Level4Stress,
    RiskMetric,
    RiskUnitType,
    StressScenarioResult,
)


def _scenario_return(
    slots: list[AllocationSlot],
    shocks: dict[AssetClass, Decimal],
) -> tuple[Decimal, dict[str, Decimal]]:
    by_class: dict[str, Decimal] = {}
    total = Decimal("0")
    for slot in slots:
        shock = shocks.get(slot.asset_class, Decimal("0"))
        contribution = slot.weight * shock
        by_class[slot.asset_class.value] = contribution
        total += contribution
    return total, by_class


def evaluate_stress(
    slots: list[AllocationSlot],
    *,
    notional_usd: Decimal | None,
    mark_source: str,
    assumptions: RiskAssumptions,
    stress_filter: str | None = None,
) -> Level4Stress:
    scenarios: list[StressScenarioResult] = []
    packs = assumptions.stress_scenarios
    if stress_filter is not None:
        if stress_filter not in packs:
            raise ValueError(f"unknown stress_pack: {stress_filter}")
        packs = {stress_filter: packs[stress_filter]}
    for name, shocks in packs.items():
        portfolio_return, by_class = _scenario_return(slots, shocks)
        return_metric = RiskMetric(
            value=portfolio_return,
            unit_type=RiskUnitType.RETURN_FRACTION,
            method="named_stress_replay",
            mark_source=mark_source,
            approximation="linear_sleeve_shock_sum_no_cross_gamma",
        )
        dollar_pnl = None
        if notional_usd is not None:
            dollar_pnl = RiskMetric(
                value=portfolio_return * notional_usd,
                unit_type=RiskUnitType.USD,
                method="named_stress_replay",
                mark_source=mark_source,
                currency="USD",
                approximation="linear_notional_scaling",
            )
        scenarios.append(
            StressScenarioResult(
                name=name,
                portfolio_return=return_metric,
                dollar_pnl=dollar_pnl,
                by_class=by_class,
            )
        )
    return Level4Stress(scenarios=scenarios)
