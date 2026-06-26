"""Risk evaluation by asset class — Level 2 variance contributions."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.assumptions import RiskAssumptions
from warehouse.research.risk.covariance import (
    CovarianceResult,
    SleeveRiskState,
)
from warehouse.research.risk.models import (
    AllocationSlot,
    ClassRiskContribution,
    MeasurementMode,
)


def resolve_measurement(slot: AllocationSlot) -> MeasurementMode:
    if slot.measurement != MeasurementMode.AUTO:
        return slot.measurement
    if slot.asset_class.value == "alternatives" or slot.liquidity_tier >= 3:
        return MeasurementMode.FERMI
    if slot.liquidity_tier >= 2:
        return MeasurementMode.FERMI
    return MeasurementMode.MEASURABLE


def sleeve_annual_volatility(
    slot: AllocationSlot,
    assumptions: RiskAssumptions,
) -> Decimal:
    measurement = resolve_measurement(slot)
    annual_vol = assumptions.class_annual_vol[slot.asset_class]
    if measurement == MeasurementMode.FERMI:
        annual_vol = annual_vol * assumptions.fermi_vol_multiplier
    return annual_vol


def build_sleeve_states(
    slots: list[AllocationSlot],
    assumptions: RiskAssumptions,
) -> list[SleeveRiskState]:
    return [
        SleeveRiskState(
            slot=slot,
            annual_volatility=sleeve_annual_volatility(slot, assumptions),
            measurement=resolve_measurement(slot).value,
        )
        for slot in slots
    ]


def evaluate_class_contributions(
    states: list[SleeveRiskState],
    cov_result: CovarianceResult,
    assumptions: RiskAssumptions,
) -> list[ClassRiskContribution]:
    rows: list[ClassRiskContribution] = []
    for state, pct_var in zip(
        states, cov_result.pct_variance_contributions, strict=True
    ):
        slot = state.slot
        rows.append(
            ClassRiskContribution(
                asset_class=slot.asset_class.value,
                weight=slot.weight,
                annual_volatility=state.annual_volatility,
                pct_variance_contribution=pct_var,
                pct_es_contribution=pct_var,
                expected_return=slot.weight
                * assumptions.class_expected_return[slot.asset_class],
                measurement=MeasurementMode(state.measurement),
                liquidity_tier=slot.liquidity_tier,
            )
        )
    return rows


def portfolio_expected_return(
    states: list[SleeveRiskState],
    assumptions: RiskAssumptions,
) -> Decimal:
    return sum(
        (
            s.slot.weight
            * assumptions.class_expected_return[s.slot.asset_class]
            for s in states
        ),
        Decimal("0"),
    )
