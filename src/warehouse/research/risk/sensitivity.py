"""Level 3 native sensitivity units per asset class."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.assumptions import DEFAULT_BETA, DEFAULT_DURATION_YEARS
from warehouse.research.risk.by_class import resolve_measurement
from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    MeasurementMode,
    RiskMetric,
    RiskUnitType,
    SleeveSensitivity,
)


def _native_unit(asset_class: AssetClass) -> RiskUnitType:
    if asset_class == AssetClass.EQUITY:
        return RiskUnitType.BETA
    if asset_class == AssetClass.FIXED_INCOME:
        return RiskUnitType.DURATION_YEARS
    if asset_class in (AssetClass.COMMODITIES, AssetClass.FX):
        return RiskUnitType.BETA
    if asset_class == AssetClass.ALTERNATIVES:
        return RiskUnitType.FERMI_ESTIMATE
    return RiskUnitType.DURATION_YEARS


def native_sensitivity_value(slot: AllocationSlot) -> Decimal:
    if slot.asset_class == AssetClass.EQUITY:
        return slot.beta if slot.beta is not None else DEFAULT_BETA[slot.asset_class]
    if slot.asset_class == AssetClass.FIXED_INCOME:
        if slot.duration_years is not None:
            return slot.duration_years
        return DEFAULT_DURATION_YEARS[slot.asset_class]
    if slot.asset_class == AssetClass.CASH:
        return DEFAULT_DURATION_YEARS[slot.asset_class]
    if slot.asset_class in (AssetClass.COMMODITIES, AssetClass.FX):
        return DEFAULT_BETA[slot.asset_class]
    return DEFAULT_BETA[slot.asset_class]


def evaluate_sleeve_sensitivity(slot: AllocationSlot) -> SleeveSensitivity:
    measurement = resolve_measurement(slot)
    unit = _native_unit(slot.asset_class)
    value = native_sensitivity_value(slot)
    method = "observed" if measurement == MeasurementMode.MEASURABLE else "fermi"
    return SleeveSensitivity(
        asset_class=slot.asset_class.value,
        weight=slot.weight,
        native_unit=unit,
        value=RiskMetric(
            value=value,
            unit_type=unit,
            method=method,
            mark_source="position" if slot.beta or slot.duration_years else "model_prior",
            approximation=None if measurement == MeasurementMode.MEASURABLE else "fermi_prior",
        ),
        measurement=measurement,
    )


def evaluate_sensitivities(slots: list[AllocationSlot]) -> list[SleeveSensitivity]:
    return [evaluate_sleeve_sensitivity(slot) for slot in slots]
