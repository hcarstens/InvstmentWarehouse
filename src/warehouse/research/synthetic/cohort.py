"""Cohort profiles — conditioned sleeve priors (not uniform Dirichlet)."""

from __future__ import annotations

import random
from decimal import Decimal

from warehouse.research.risk.models import AssetClass

GENERATOR_VERSION = "2026.03"
AXIOM_SET_HASH = "hnw-sdg-v1"

COHORT_IDS = (
    "general_hnw",
    "uhnw_inherited",
    "founder_executive",
    "concentrated_stress",
)

# (min, max) weight ranges per cohort — docs/research/hnw_portfolios.md
_SLEEVE_RANGES: dict[str, dict[AssetClass, tuple[float, float]]] = {
    "general_hnw": {
        AssetClass.EQUITY: (0.45, 0.65),
        AssetClass.FIXED_INCOME: (0.15, 0.30),
        AssetClass.CASH: (0.05, 0.15),
        AssetClass.ALTERNATIVES: (0.05, 0.15),
    },
    "uhnw_inherited": {
        AssetClass.EQUITY: (0.35, 0.50),
        AssetClass.ALTERNATIVES: (0.20, 0.35),
        AssetClass.FIXED_INCOME: (0.10, 0.20),
        AssetClass.CASH: (0.05, 0.10),
        AssetClass.COMMODITIES: (0.02, 0.08),
    },
    "founder_executive": {
        AssetClass.EQUITY: (0.50, 0.80),
        AssetClass.ALTERNATIVES: (0.05, 0.20),
        AssetClass.FIXED_INCOME: (0.05, 0.15),
        AssetClass.CASH: (0.05, 0.15),
    },
    "concentrated_stress": {
        AssetClass.EQUITY: (0.70, 0.90),
        AssetClass.FIXED_INCOME: (0.05, 0.15),
        AssetClass.CASH: (0.05, 0.10),
    },
}

_RUNG_COHORT: dict[int, str] = {
    3: "general_hnw",
    4: "concentrated_stress",
}


def default_cohort_for_rung(rung: int) -> str:
    if rung not in _RUNG_COHORT:
        raise ValueError(f"no default cohort for rung {rung}")
    return _RUNG_COHORT[rung]


def sample_sleeve_weights_uniform(
    cohort_id: str, seed: int
) -> dict[AssetClass, Decimal]:
    """Negation of cohort-conditioned priors — uniform on available sleeves."""
    if cohort_id not in _SLEEVE_RANGES:
        raise KeyError(f"unknown cohort_id: {cohort_id}")
    sleeves = list(_SLEEVE_RANGES[cohort_id].keys())
    raw = {asset_class: Decimal("1") for asset_class in sleeves}
    total = Decimal(str(len(sleeves)))
    keys = list(raw.keys())
    weights: dict[AssetClass, Decimal] = {}
    assigned = Decimal("0")
    for index, asset_class in enumerate(keys):
        if index == len(keys) - 1:
            weights[asset_class] = Decimal("1") - assigned
        else:
            weight = (Decimal("1") / total).quantize(Decimal("0.0000001"))
            weights[asset_class] = weight
            assigned += weight
    return weights


def sample_sleeve_weights(
    cohort_id: str, seed: int
) -> dict[AssetClass, Decimal]:
    if cohort_id not in _SLEEVE_RANGES:
        raise KeyError(f"unknown cohort_id: {cohort_id}")
    rng = random.Random(seed)
    ranges = _SLEEVE_RANGES[cohort_id]
    raw = {
        asset_class: Decimal(str(rng.uniform(low, high)))
        for asset_class, (low, high) in ranges.items()
    }
    total = sum(raw.values(), Decimal("0"))
    keys = list(raw.keys())
    weights: dict[AssetClass, Decimal] = {}
    assigned = Decimal("0")
    for index, asset_class in enumerate(keys):
        if index == len(keys) - 1:
            weights[asset_class] = Decimal("1") - assigned
        else:
            weight = (raw[asset_class] / total).quantize(Decimal("0.0000001"))
            weights[asset_class] = weight
            assigned += weight
    return weights


def tension_tags_for(cohort_id: str) -> list[str]:
    if cohort_id == "concentrated_stress":
        return ["concentration_cap", "liquidity_mismatch"]
    if cohort_id == "founder_executive":
        return ["issuer_concentration"]
    if cohort_id == "uhnw_inherited":
        return ["illiquid_alts", "trust_structure"]
    return ["ips_drift_headroom"]
