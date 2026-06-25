"""Risk API request and response models."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class MeasurementMode(StrEnum):
    MEASURABLE = "measurable"
    FERMI = "fermi"
    AUTO = "auto"


class AssetClass(StrEnum):
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    COMMODITIES = "commodities"
    FX = "fx"
    ALTERNATIVES = "alternatives"
    CASH = "cash"


class AllocationSlot(BaseModel):
    asset_class: AssetClass
    weight: Decimal = Field(ge=0, le=1)
    duration_years: Decimal | None = Field(default=None, ge=0)
    liquidity_tier: int = Field(default=1, ge=1, le=3)
    measurement: MeasurementMode = MeasurementMode.AUTO
    label: str | None = None


class AssetPortfolio(BaseModel):
    portfolio_id: str | None = None
    allocations: list[AllocationSlot] = Field(min_length=1)

    @field_validator("allocations")
    @classmethod
    def weights_sum_to_one(cls, slots: list[AllocationSlot]) -> list[AllocationSlot]:
        total = sum((s.weight for s in slots), Decimal("0"))
        if abs(total - Decimal("1")) > Decimal("0.0001"):
            raise ValueError(f"allocation weights must sum to 1.0, got {total}")
        return slots


class RiskHorizon(BaseModel):
    years: Decimal = Field(gt=0, le=50)

    @classmethod
    def parse(cls, value: str | int | float | Decimal) -> RiskHorizon:
        if isinstance(value, str):
            text = value.strip().lower()
            if text.endswith("y"):
                return cls(years=Decimal(text[:-1]))
            return cls(years=Decimal(text))
        return cls(years=Decimal(str(value)))


class ClassRiskContribution(BaseModel):
    asset_class: str
    weight: Decimal
    annual_volatility: Decimal
    horizon_volatility: Decimal
    risk_contribution: Decimal
    expected_return: Decimal
    measurement: MeasurementMode
    liquidity_tier: int


class DurationBucketRisk(BaseModel):
    bucket: str
    weight: Decimal
    avg_duration_years: Decimal | None
    horizon_mismatch: Decimal
    risk_contribution: Decimal


class MeasurementSummary(BaseModel):
    measurable_weight: Decimal
    fermi_weight: Decimal
    fermi_risk_share: Decimal


class PortfolioRiskReport(BaseModel):
    portfolio_id: str | None
    horizon_years: Decimal
    total_risk: Decimal
    expected_return: Decimal
    confidence_low: Decimal
    confidence_high: Decimal
    diversification_factor: Decimal
    by_class: list[ClassRiskContribution]
    by_duration: list[DurationBucketRisk]
    measurement_summary: MeasurementSummary
    model_version: str
    input_fingerprint: str
