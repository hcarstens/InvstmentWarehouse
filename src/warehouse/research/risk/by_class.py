"""Risk evaluation by asset class."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.assumptions import (
    CLASS_ANNUAL_VOL,
    CLASS_EXPECTED_RETURN,
    FERMI_VOL_MULTIPLIER,
)
from warehouse.research.risk.models import (
    AllocationSlot,
    ClassRiskContribution,
    MeasurementMode,
    RiskHorizon,
)


def resolve_measurement(slot: AllocationSlot) -> MeasurementMode:
    if slot.measurement != MeasurementMode.AUTO:
        return slot.measurement
    if slot.asset_class.value == "alternatives" or slot.liquidity_tier >= 3:
        return MeasurementMode.FERMI
    if slot.liquidity_tier >= 2:
        return MeasurementMode.FERMI
    return MeasurementMode.MEASURABLE


def horizon_volatility(annual_vol: Decimal, horizon: RiskHorizon) -> Decimal:
    return annual_vol * horizon.years.sqrt()


def evaluate_class_risk(
    slot: AllocationSlot,
    horizon: RiskHorizon,
) -> ClassRiskContribution:
    measurement = resolve_measurement(slot)
    annual_vol = CLASS_ANNUAL_VOL[slot.asset_class]
    if measurement == MeasurementMode.FERMI:
        annual_vol = annual_vol * FERMI_VOL_MULTIPLIER
    h_vol = horizon_volatility(annual_vol, horizon)
    contribution = slot.weight * h_vol
    expected = slot.weight * CLASS_EXPECTED_RETURN[slot.asset_class]
    return ClassRiskContribution(
        asset_class=slot.asset_class.value,
        weight=slot.weight,
        annual_volatility=annual_vol,
        horizon_volatility=h_vol,
        risk_contribution=contribution,
        expected_return=expected,
        measurement=measurement,
        liquidity_tier=slot.liquidity_tier,
    )


def aggregate_class_risk(
    contributions: list[ClassRiskContribution],
    diversification: Decimal,
) -> Decimal:
    if not contributions:
        return Decimal("0")
    sum_sq = sum((c.risk_contribution**2 for c in contributions), Decimal("0"))
    return sum_sq.sqrt() * diversification
