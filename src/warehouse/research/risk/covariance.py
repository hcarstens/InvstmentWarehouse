"""Covariance-based portfolio variance and risk contributions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from warehouse.research.risk.assumptions import RiskAssumptions
from warehouse.research.risk.models import AllocationSlot


@dataclass(frozen=True)
class SleeveRiskState:
    slot: AllocationSlot
    annual_volatility: Decimal
    measurement: str


@dataclass(frozen=True)
class CovarianceResult:
    portfolio_variance: Decimal
    portfolio_volatility: Decimal
    pct_variance_contributions: list[Decimal]
    marginal_variance: list[Decimal]


def portfolio_covariance(
    states: list[SleeveRiskState],
    assumptions: RiskAssumptions,
) -> CovarianceResult:
    n = len(states)
    if n == 0:
        zero = Decimal("0")
        return CovarianceResult(zero, zero, [], [])

    weights = [s.slot.weight for s in states]
    vols = [s.annual_volatility for s in states]
    classes = [s.slot.asset_class for s in states]

    cov: list[list[Decimal]] = [[Decimal("0")] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            rho = assumptions.pairwise_correlation(classes[i], classes[j])
            cov[i][j] = vols[i] * vols[j] * rho

    portfolio_variance = Decimal("0")
    for i in range(n):
        for j in range(n):
            portfolio_variance += weights[i] * weights[j] * cov[i][j]

    portfolio_volatility = portfolio_variance.sqrt(
    ) if portfolio_variance > 0 else Decimal("0")

    marginal_variance: list[Decimal] = []
    for i in range(n):
        cov_times_w = sum(cov[i][j] * weights[j] for j in range(n))
        marginal_variance.append(weights[i] * cov_times_w)

    if portfolio_variance > 0:
        pct = [mv / portfolio_variance for mv in marginal_variance]
    else:
        pct = [Decimal("0")] * n

    return CovarianceResult(
        portfolio_variance=portfolio_variance,
        portfolio_volatility=portfolio_volatility,
        pct_variance_contributions=pct,
        marginal_variance=marginal_variance,
    )
