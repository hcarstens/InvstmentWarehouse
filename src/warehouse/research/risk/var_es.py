"""Parametric VaR and ES — Level 1 dollar tail units."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.assumptions import RiskAssumptions
from warehouse.research.risk.models import RiskMetric, RiskUnitType


def _alpha_key(alpha: float) -> str:
    return f"{alpha:.3f}".rstrip("0").rstrip(".")


def horizon_scale(annual_vol: Decimal, horizon_years: Decimal) -> Decimal:
    return annual_vol * horizon_years.sqrt()


def horizon_expected_return(
    annual_return: Decimal, horizon_years: Decimal
) -> Decimal:
    return annual_return * horizon_years


def parametric_var(
    annual_vol: Decimal,
    annual_return: Decimal,
    horizon_years: Decimal,
    alpha: float,
    *,
    assumptions: RiskAssumptions,
    mark_source: str,
) -> RiskMetric:
    sigma_h = horizon_scale(annual_vol, horizon_years)
    mu_h = horizon_expected_return(annual_return, horizon_years)
    z = assumptions.z_scores[_alpha_key(alpha)]
    value = z * sigma_h - mu_h
    return RiskMetric(
        value=value,
        unit_type=RiskUnitType.RETURN_FRACTION,
        horizon_years=horizon_years,
        confidence=Decimal(str(alpha)),
        window_days=assumptions.vol_window_days,
        method="parametric",
        mark_source=mark_source,
        approximation="multivariate_normal_via_portfolio_sigma",
    )


def parametric_es(
    annual_vol: Decimal,
    annual_return: Decimal,
    horizon_years: Decimal,
    alpha: float,
    *,
    assumptions: RiskAssumptions,
    mark_source: str,
) -> RiskMetric:
    sigma_h = horizon_scale(annual_vol, horizon_years)
    mu_h = horizon_expected_return(annual_return, horizon_years)
    es_mult = assumptions.es_multipliers[_alpha_key(alpha)]
    value = es_mult * sigma_h - mu_h
    return RiskMetric(
        value=value,
        unit_type=RiskUnitType.RETURN_FRACTION,
        horizon_years=horizon_years,
        confidence=Decimal(str(alpha)),
        window_days=assumptions.vol_window_days,
        method="parametric",
        mark_source=mark_source,
        approximation="normal_es_from_portfolio_sigma",
    )


def dollar_tail(metric: RiskMetric, notional_usd: Decimal) -> RiskMetric:
    return RiskMetric(
        value=metric.value * notional_usd,
        unit_type=RiskUnitType.USD,
        horizon_years=metric.horizon_years,
        confidence=metric.confidence,
        window_days=metric.window_days,
        method=metric.method,
        mark_source=metric.mark_source,
        currency="USD",
        approximation=metric.approximation,
    )
