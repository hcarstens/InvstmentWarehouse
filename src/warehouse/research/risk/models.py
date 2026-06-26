"""Risk API models — unit hierarchy per docs/research/risk_units_measures.md."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MeasurementMode(StrEnum):
    MEASURABLE = "measurable"
    FERMI = "fermi"
    AUTO = "auto"


class RiskUnitType(StrEnum):
    SIGMA_ANNUALIZED = "sigma_annualized"
    SIGMA_HORIZON = "sigma_horizon"
    RETURN_FRACTION = "return_fraction"
    USD = "usd"
    PCT_VARIANCE = "pct_variance"
    BETA = "beta"
    DURATION_YEARS = "duration_years"
    LIQUIDITY_DAYS = "liquidity_days"
    FERMI_ESTIMATE = "fermi_estimate"


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
    beta: Decimal | None = Field(default=None, ge=0)
    liquidity_tier: int = Field(default=1, ge=1, le=3)
    measurement: MeasurementMode = MeasurementMode.AUTO
    label: str | None = None


class AssetPortfolio(BaseModel):
    portfolio_id: str | None = None
    allocations: list[AllocationSlot] = Field(min_length=1)
    source: str = "synthetic"
    complexity: int | None = None

    @field_validator("allocations")
    @classmethod
    def weights_sum_to_one(cls, slots: list[AllocationSlot]) -> list[AllocationSlot]:
        total = sum((s.weight for s in slots), Decimal("0"))
        if abs(total - Decimal("1")) > Decimal("0.0001"):
            raise ValueError(
                f"allocation weights must sum to 1.0, got {total}")
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


class ScenarioSet(StrEnum):
    NONE = "none"
    HIGH_RISK = "high_risk"
    LOW_RISK = "low_risk"
    ALL = "all"


class ManifestOverlay(BaseModel):
    """Declarative perturbation — NOT a second full manifest."""

    weight_tilts: dict[AssetClass, Decimal] = Field(default_factory=dict)
    add_sleeves: list[AllocationSlot] = Field(default_factory=list)
    drop_sleeves: list[AssetClass] = Field(default_factory=list)
    stress_pack: str | None = None
    label: str | None = None


class RiskRequest(BaseModel):
    horizon: RiskHorizon
    notional_usd: Decimal | None = None
    run_scenarios: ScenarioSet = ScenarioSet.NONE
    overlay: ManifestOverlay | None = None


class MetricDelta(BaseModel):
    metric: str
    baseline: Decimal
    proposed: Decimal
    delta: Decimal
    pct_change: Decimal | None = None


class RiskDeltas(BaseModel):
    model_config = ConfigDict(frozen=True)

    overlay_label: str | None
    baseline_fingerprint: str
    proposed_fingerprint: str
    headline: list[MetricDelta]
    by_class_variance_delta: dict[str, Decimal]


class RiskResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    report: PortfolioRiskReport
    scenarios: dict[str, PortfolioRiskReport] = Field(default_factory=dict)
    deltas: RiskDeltas | None = None


class RiskMetric(BaseModel):
    """Minimum disclosure: unit, α, h, window, mark_source on every metric."""

    value: Decimal
    unit_type: RiskUnitType
    horizon_years: Decimal | None = None
    confidence: Decimal | None = None
    window_days: int | None = None
    method: str | None = None
    mark_source: str = "model_prior"
    currency: str | None = None
    approximation: str | None = None


class RiskManifestMeta(BaseModel):
    currency: str = "USD"
    mark_source: str = "model_prior"
    vol_window_days: int
    stress_pack_version: str
    assumption_regime: str = "base"


class Level1PortfolioRisk(BaseModel):
    annualized_volatility: RiskMetric
    horizon_volatility: RiskMetric
    expected_return: RiskMetric
    parametric_var: RiskMetric
    parametric_es: RiskMetric
    dollar_var: RiskMetric | None = None
    dollar_es: RiskMetric | None = None
    confidence_low: RiskMetric
    confidence_high: RiskMetric


class ClassRiskContribution(BaseModel):
    asset_class: str
    weight: Decimal
    annual_volatility: Decimal
    pct_variance_contribution: Decimal
    pct_es_contribution: Decimal
    expected_return: Decimal
    measurement: MeasurementMode
    liquidity_tier: int


class DurationBucketRisk(BaseModel):
    bucket: str
    weight: Decimal
    avg_duration_years: Decimal | None
    horizon_mismatch: Decimal
    pct_variance_contribution: Decimal


class Level2Contributions(BaseModel):
    unit_type: RiskUnitType = RiskUnitType.PCT_VARIANCE
    by_class: list[ClassRiskContribution]
    by_duration: list[DurationBucketRisk]


class SleeveSensitivity(BaseModel):
    asset_class: str
    weight: Decimal
    native_unit: RiskUnitType
    value: RiskMetric
    measurement: MeasurementMode


class Level3Sensitivities(BaseModel):
    by_sleeve: list[SleeveSensitivity]


class StressScenarioResult(BaseModel):
    name: str
    portfolio_return: RiskMetric
    dollar_pnl: RiskMetric | None = None
    by_class: dict[str, Decimal]


class Level4Stress(BaseModel):
    method: str = "named_stress_replay"
    scenarios: list[StressScenarioResult]


class LiquidityTierRisk(BaseModel):
    tier: int
    weight: Decimal
    days_to_liquidate: RiskMetric


class LiquidityRisk(BaseModel):
    unit_type: RiskUnitType = RiskUnitType.LIQUIDITY_DAYS
    weighted_days: RiskMetric
    by_tier: list[LiquidityTierRisk]


class MeasurementSummary(BaseModel):
    measurable_weight: Decimal
    fermi_weight: Decimal
    fermi_risk_share: Decimal


class PortfolioRiskReport(BaseModel):
    portfolio_id: str | None
    horizon_years: Decimal
    model_version: str
    input_fingerprint: str
    manifest: RiskManifestMeta
    level_1_portfolio: Level1PortfolioRisk
    level_2_contributions: Level2Contributions
    level_3_sensitivities: Level3Sensitivities
    level_4_stress: Level4Stress
    liquidity: LiquidityRisk
    measurement_summary: MeasurementSummary
    aggregation_note: str
