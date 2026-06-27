"""Synthetic IPS emission — cohort-conditioned policy from sampled weights."""

from __future__ import annotations

import random
from decimal import Decimal

from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.research.risk.models import AssetClass
from warehouse.research.synthetic.ips_cohort import (
    DEFAULT_IPS_EFFECTIVE_DATE,
    CohortIpsPriors,
    cohort_ips_priors,
)

_WEIGHT_QUANT = Decimal("0.0000001")


def _asset_to_ips_sleeve(asset_class: AssetClass) -> IpsSleeve:
    return IpsSleeve(asset_class.value)


def _resolve_concentration_limit(
    cohort_id: str,
    priors: CohortIpsPriors,
    seed: int,
    weights: dict[AssetClass, Decimal],
) -> Decimal:
    if priors.concentration_limit_pct is not None:
        return priors.concentration_limit_pct
    rng = random.Random(seed + 17)
    equity_weight = weights.get(AssetClass.EQUITY, Decimal("0"))
    if priors.concentration_issuer_range is not None:
        low, high = priors.concentration_issuer_range
        issuer_cap = Decimal(str(rng.uniform(low, high))).quantize(
            Decimal("0.01")
        )
        return (issuer_cap * equity_weight).quantize(Decimal("0.01"))
    if priors.concentration_portfolio_range is not None:
        low, high = priors.concentration_portfolio_range
        return Decimal(str(rng.uniform(low, high))).quantize(Decimal("0.01"))
    raise ValueError(
        f"cohort {cohort_id} has no concentration prior configured"
    )


def _allocation_target(
    *,
    cohort_id: str,
    sleeve: IpsSleeve,
    weight: Decimal,
    band: Decimal,
) -> AllocationTarget:
    if cohort_id == "concentrated_stress" and sleeve == IpsSleeve.EQUITY:
        max_weight = (weight - Decimal("0.005")).quantize(_WEIGHT_QUANT)
        min_weight = max(Decimal("0"), max_weight - band).quantize(
            _WEIGHT_QUANT
        )
        target_weight = max_weight
    else:
        target_weight = weight.quantize(_WEIGHT_QUANT)
        min_weight = max(Decimal("0"), target_weight - band).quantize(
            _WEIGHT_QUANT
        )
        max_weight = min(Decimal("1"), target_weight + band).quantize(
            _WEIGHT_QUANT
        )
    return AllocationTarget(
        asset_class=sleeve,
        min_weight=min_weight,
        max_weight=max_weight,
        target_weight=target_weight,
    )


def _sample_restricted_securities(
    cohort_id: str, seed: int, rung: int
) -> list[str]:
    if rung < 4:
        return []
    rng = random.Random(seed + 1000)
    if cohort_id == "uhnw_inherited" and rng.random() < 0.3:
        return ["VTI"]
    if cohort_id == "founder_executive" and rng.random() < 0.4:
        return ["BND"]
    return []


def emit_ips_for_cohort(
    *,
    cohort_id: str,
    seed: int,
    household_id: str,
    weights: dict[AssetClass, Decimal],
    rung: int = 3,
    ips_id: str | None = None,
    effective_date: str = DEFAULT_IPS_EFFECTIVE_DATE,
) -> InvestmentPolicyStatement:
    """Build IPS allocation bands from sleeve weights + cohort priors."""
    priors = cohort_ips_priors(cohort_id)
    concentration = _resolve_concentration_limit(
        cohort_id, priors, seed, weights
    )
    allocation_targets: list[AllocationTarget] = []
    for asset_class in sorted(weights, key=lambda ac: ac.value):
        weight = weights[asset_class]
        if weight <= 0:
            continue
        allocation_targets.append(
            _allocation_target(
                cohort_id=cohort_id,
                sleeve=_asset_to_ips_sleeve(asset_class),
                weight=weight,
                band=priors.allocation_band_pct,
            )
        )
    if not allocation_targets:
        raise ValueError(
            f"no positive sleeve weights for cohort {cohort_id} seed {seed}"
        )
    return InvestmentPolicyStatement(
        ips_id=ips_id or f"ips_{household_id}_v1",
        household_id=household_id,
        version=1,
        effective_date=effective_date,
        allocation_targets=allocation_targets,
        restricted_securities=_sample_restricted_securities(
            cohort_id, seed, rung
        ),
        concentration_limit_pct=concentration,
        liquidity_tier_min_pct=priors.liquidity_tier_min_pct,
        turnover_budget_pct=priors.turnover_budget_pct,
    )
