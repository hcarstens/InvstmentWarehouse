"""Version-pinned risk priors — vol, correlation, stress, liquidity.

Tune via risk_model_version / risk_stress_pack_version,
not per-request overrides.
See docs/research/risk_units_measures.md and docs/research/portfolio_risk.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from warehouse.research.risk.models import AssetClass

# Annualized return and vol priors (Level 1 covariance inputs).
CLASS_ANNUAL_VOL: dict[AssetClass, Decimal] = {
    AssetClass.EQUITY: Decimal("0.160"),
    AssetClass.FIXED_INCOME: Decimal("0.060"),
    AssetClass.COMMODITIES: Decimal("0.200"),
    AssetClass.FX: Decimal("0.080"),
    AssetClass.ALTERNATIVES: Decimal("0.250"),
    AssetClass.CASH: Decimal("0.010"),
}

CLASS_EXPECTED_RETURN: dict[AssetClass, Decimal] = {
    AssetClass.EQUITY: Decimal("0.070"),
    AssetClass.FIXED_INCOME: Decimal("0.040"),
    AssetClass.COMMODITIES: Decimal("0.050"),
    AssetClass.FX: Decimal("0.020"),
    AssetClass.ALTERNATIVES: Decimal("0.090"),
    AssetClass.CASH: Decimal("0.030"),
}

DEFAULT_CLASS_CORRELATION = Decimal("0.25")

# Pairwise correlations — normal-regime priors; stress pack handles crisis
# separately.
CLASS_CORRELATIONS: dict[frozenset[AssetClass], Decimal] = {
    frozenset({AssetClass.EQUITY, AssetClass.FIXED_INCOME}): Decimal("-0.20"),
    frozenset({AssetClass.EQUITY, AssetClass.COMMODITIES}): Decimal("0.35"),
    frozenset({AssetClass.EQUITY, AssetClass.FX}): Decimal("-0.15"),
    frozenset({AssetClass.EQUITY, AssetClass.ALTERNATIVES}): Decimal("0.55"),
    frozenset({AssetClass.FIXED_INCOME, AssetClass.COMMODITIES}): Decimal(
        "0.10"
    ),
    frozenset({AssetClass.FIXED_INCOME, AssetClass.FX}): Decimal("0.20"),
    frozenset({AssetClass.FIXED_INCOME, AssetClass.ALTERNATIVES}): Decimal(
        "0.30"
    ),
    frozenset({AssetClass.FIXED_INCOME, AssetClass.CASH}): Decimal("0.05"),
    frozenset({AssetClass.COMMODITIES, AssetClass.FX}): Decimal("0.15"),
    frozenset({AssetClass.COMMODITIES, AssetClass.ALTERNATIVES}): Decimal(
        "0.40"
    ),
    frozenset({AssetClass.FX, AssetClass.ALTERNATIVES}): Decimal("0.25"),
    frozenset({AssetClass.EQUITY, AssetClass.CASH}): Decimal("0.00"),
    frozenset({AssetClass.COMMODITIES, AssetClass.CASH}): Decimal("0.00"),
    frozenset({AssetClass.FX, AssetClass.CASH}): Decimal("0.00"),
    frozenset({AssetClass.ALTERNATIVES, AssetClass.CASH}): Decimal("0.00"),
}

DEFAULT_BETA: dict[AssetClass, Decimal] = {
    AssetClass.EQUITY: Decimal("1.0"),
    AssetClass.FIXED_INCOME: Decimal("0.0"),
    AssetClass.COMMODITIES: Decimal("0.5"),
    AssetClass.FX: Decimal("0.3"),
    AssetClass.ALTERNATIVES: Decimal("0.6"),
    AssetClass.CASH: Decimal("0.0"),
}

DEFAULT_DURATION_YEARS: dict[AssetClass, Decimal] = {
    AssetClass.EQUITY: Decimal("0"),
    AssetClass.FIXED_INCOME: Decimal("6.0"),
    AssetClass.COMMODITIES: Decimal("0"),
    AssetClass.FX: Decimal("0"),
    AssetClass.ALTERNATIVES: Decimal("7.0"),
    AssetClass.CASH: Decimal("0.25"),
}

FERMI_VOL_MULTIPLIER = Decimal("1.35")

Z_SCORES: dict[str, Decimal] = {
    "0.95": Decimal("1.644853626951472"),
    "0.975": Decimal("1.959963984540054"),
}

ES_MULTIPLIERS: dict[str, Decimal] = {
    "0.95": Decimal("2.062671"),
    "0.975": Decimal("2.337803"),
}

LIQUIDITY_DAYS_BY_TIER: dict[int, Decimal] = {
    1: Decimal("1"),
    2: Decimal("30"),
    3: Decimal("180"),
}

STRESS_SCENARIOS: dict[str, dict[AssetClass, Decimal]] = {
    "2008_liquidity": {
        AssetClass.EQUITY: Decimal("-0.38"),
        AssetClass.FIXED_INCOME: Decimal("0.05"),
        AssetClass.COMMODITIES: Decimal("-0.25"),
        AssetClass.FX: Decimal("0.08"),
        AssetClass.ALTERNATIVES: Decimal("-0.30"),
        AssetClass.CASH: Decimal("0.01"),
    },
    "2020_pandemic": {
        AssetClass.EQUITY: Decimal("-0.34"),
        AssetClass.FIXED_INCOME: Decimal("0.08"),
        AssetClass.COMMODITIES: Decimal("-0.28"),
        AssetClass.FX: Decimal("0.05"),
        AssetClass.ALTERNATIVES: Decimal("-0.22"),
        AssetClass.CASH: Decimal("0.00"),
    },
    "2022_inflation": {
        AssetClass.EQUITY: Decimal("-0.25"),
        AssetClass.FIXED_INCOME: Decimal("-0.15"),
        AssetClass.COMMODITIES: Decimal("0.12"),
        AssetClass.FX: Decimal("-0.05"),
        AssetClass.ALTERNATIVES: Decimal("-0.10"),
        AssetClass.CASH: Decimal("-0.02"),
    },
}

MODEL_VERSION = "2026.02"
STRESS_PACK_VERSION = "2026.01"
VOL_WINDOW_DAYS = 252
VAR_ALPHA = 0.95
ES_ALPHA = 0.975
FERMI_CONFIDENCE_WIDTH = 0.15


@dataclass(frozen=True)
class RiskAssumptions:
    """Frozen, version-pinned assumption set for one regime."""

    regime: str
    model_version: str
    stress_pack_version: str
    vol_window_days: int
    var_alpha: float
    es_alpha: float
    fermi_confidence_width: float
    class_annual_vol: dict[AssetClass, Decimal]
    class_expected_return: dict[AssetClass, Decimal]
    default_class_correlation: Decimal
    class_correlations: dict[frozenset[AssetClass], Decimal]
    fermi_vol_multiplier: Decimal
    z_scores: dict[str, Decimal]
    es_multipliers: dict[str, Decimal]
    stress_scenarios: dict[str, dict[AssetClass, Decimal]]

    def pairwise_correlation(
        self,
        left: AssetClass,
        right: AssetClass,
    ) -> Decimal:
        if left == right:
            return Decimal("1")
        return self.class_correlations.get(
            frozenset({left, right}),
            self.default_class_correlation,
        )


def base_assumption_fields() -> dict[str, object]:
    """Pinned defaults matching configs/development.toml risk_* keys."""
    return {
        "regime": "base",
        "model_version": MODEL_VERSION,
        "stress_pack_version": STRESS_PACK_VERSION,
        "vol_window_days": VOL_WINDOW_DAYS,
        "var_alpha": VAR_ALPHA,
        "es_alpha": ES_ALPHA,
        "fermi_confidence_width": FERMI_CONFIDENCE_WIDTH,
        "class_annual_vol": dict(CLASS_ANNUAL_VOL),
        "class_expected_return": dict(CLASS_EXPECTED_RETURN),
        "default_class_correlation": DEFAULT_CLASS_CORRELATION,
        "class_correlations": dict(CLASS_CORRELATIONS),
        "fermi_vol_multiplier": FERMI_VOL_MULTIPLIER,
        "z_scores": dict(Z_SCORES),
        "es_multipliers": dict(ES_MULTIPLIERS),
        "stress_scenarios": {
            name: dict(shocks) for name, shocks in STRESS_SCENARIOS.items()
        },
    }


def build_assumptions(**overrides: object) -> RiskAssumptions:
    fields = base_assumption_fields()
    fields.update(overrides)
    return RiskAssumptions(**fields)  # type: ignore[arg-type]
