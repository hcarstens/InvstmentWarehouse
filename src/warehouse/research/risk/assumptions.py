"""Version-pinned risk priors — vol, correlation, stress, liquidity.

Tune via risk_model_version / risk_stress_pack_version, not per-request overrides.
See docs/research/risk_units_measures.md and docs/research/portfolio_risk.md.
"""

from __future__ import annotations

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

# Pairwise correlations — normal-regime priors; stress pack handles crisis separately.
CLASS_CORRELATIONS: dict[frozenset[AssetClass], Decimal] = {
    frozenset({AssetClass.EQUITY, AssetClass.FIXED_INCOME}): Decimal("-0.20"),
    frozenset({AssetClass.EQUITY, AssetClass.COMMODITIES}): Decimal("0.35"),
    frozenset({AssetClass.EQUITY, AssetClass.FX}): Decimal("-0.15"),
    frozenset({AssetClass.EQUITY, AssetClass.ALTERNATIVES}): Decimal("0.55"),
    frozenset({AssetClass.FIXED_INCOME, AssetClass.COMMODITIES}): Decimal("0.10"),
    frozenset({AssetClass.FIXED_INCOME, AssetClass.FX}): Decimal("0.20"),
    frozenset({AssetClass.FIXED_INCOME, AssetClass.ALTERNATIVES}): Decimal("0.30"),
    frozenset({AssetClass.FIXED_INCOME, AssetClass.CASH}): Decimal("0.05"),
    frozenset({AssetClass.COMMODITIES, AssetClass.FX}): Decimal("0.15"),
    frozenset({AssetClass.COMMODITIES, AssetClass.ALTERNATIVES}): Decimal("0.40"),
    frozenset({AssetClass.FX, AssetClass.ALTERNATIVES}): Decimal("0.25"),
    frozenset({AssetClass.EQUITY, AssetClass.CASH}): Decimal("0.00"),
    frozenset({AssetClass.COMMODITIES, AssetClass.CASH}): Decimal("0.00"),
    frozenset({AssetClass.FX, AssetClass.CASH}): Decimal("0.00"),
    frozenset({AssetClass.ALTERNATIVES, AssetClass.CASH}): Decimal("0.00"),
}

# Default linear exposures when sleeve does not supply native sensitivity.
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

# Parametric tail multipliers (standard normal).
Z_SCORES: dict[str, Decimal] = {
    "0.95": Decimal("1.644853626951472"),
    "0.975": Decimal("1.959963984540054"),
}

ES_MULTIPLIERS: dict[str, Decimal] = {
    "0.95": Decimal("2.062671"),
    "0.975": Decimal("2.337803"),
}

# Liquidity-time units: days to liquidate at 10% ADV (Level 0 / illiquid sleeves).
LIQUIDITY_DAYS_BY_TIER: dict[int, Decimal] = {
    1: Decimal("1"),
    2: Decimal("30"),
    3: Decimal("180"),
}

# Level 4 named stress replay — sleeve return shocks (return fraction).
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
