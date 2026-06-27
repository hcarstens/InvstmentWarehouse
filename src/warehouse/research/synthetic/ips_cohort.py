"""Cohort IPS priors — concentration, liquidity, allocation band width.

Derived from ``docs/synthetic_ips_implementation.md`` §3 and
``docs/research/hnw_portfolios.md`` cohort profiles.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from warehouse.research.synthetic.cohort import COHORT_IDS

_DEFAULT_EFFECTIVE_DATE = "2024-01-15"
DEFAULT_IPS_EFFECTIVE_DATE = _DEFAULT_EFFECTIVE_DATE


@dataclass(frozen=True)
class CohortIpsPriors:
    """Static IPS policy priors for a synthetic cohort."""

    allocation_band_pct: Decimal
    liquidity_tier_min_pct: Decimal
    concentration_limit_pct: Decimal | None = None
    concentration_portfolio_range: tuple[float, float] | None = None
    concentration_issuer_range: tuple[float, float] | None = None
    turnover_budget_pct: Decimal | None = None


COHORT_IPS_PRIORS: dict[str, CohortIpsPriors] = {
    "general_hnw": CohortIpsPriors(
        allocation_band_pct=Decimal("0.05"),
        concentration_limit_pct=Decimal("0.12"),
        liquidity_tier_min_pct=Decimal("0.75"),
        turnover_budget_pct=Decimal("0.15"),
    ),
    "uhnw_inherited": CohortIpsPriors(
        allocation_band_pct=Decimal("0.05"),
        concentration_limit_pct=Decimal("0.10"),
        liquidity_tier_min_pct=Decimal("0.55"),
        turnover_budget_pct=Decimal("0.12"),
    ),
    "founder_executive": CohortIpsPriors(
        allocation_band_pct=Decimal("0.08"),
        concentration_issuer_range=(0.15, 0.45),
        liquidity_tier_min_pct=Decimal("0.70"),
        turnover_budget_pct=Decimal("0.20"),
    ),
    "concentrated_stress": CohortIpsPriors(
        allocation_band_pct=Decimal("0.02"),
        concentration_portfolio_range=(0.20, 0.25),
        liquidity_tier_min_pct=Decimal("0.60"),
        turnover_budget_pct=Decimal("0.10"),
    ),
}


def cohort_ips_priors(cohort_id: str) -> CohortIpsPriors:
    if cohort_id not in COHORT_IPS_PRIORS:
        raise KeyError(f"unknown cohort_id: {cohort_id}")
    return COHORT_IPS_PRIORS[cohort_id]


def validate_cohort_ips_registry() -> None:
    """Ensure every portfolio cohort has IPS priors."""
    missing = set(COHORT_IDS) - set(COHORT_IPS_PRIORS)
    if missing:
        raise ValueError(
            f"COHORT_IPS_PRIORS missing cohorts: {sorted(missing)}"
        )


validate_cohort_ips_registry()
