"""Seeded daily-return path generator — SDG7 compositional (st5g).

Independent sample-stat oracles live in this module so tests can compare
generator output to statistics computed without reading internal state (ST2).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

GENERATOR_VERSION = "2026.06"
AXIOM_SET_HASH = "hnw-sdg-v1"
_TRADING_DAYS = 252
_EWMA_LAMBDA = 0.94


@dataclass(frozen=True)
class PathTargets:
    annual_vol: float
    lag1_autocorr: float
    excess_kurtosis: float
    vol_clustering: float


DEFAULT_TARGETS = PathTargets(
    annual_vol=0.16,
    lag1_autocorr=0.05,
    excess_kurtosis=1.5,
    vol_clustering=0.97,
)


def _daily_sigma(annual_vol: float) -> float:
    return annual_vol / math.sqrt(_TRADING_DAYS)


def _ewma_vol_series(returns: list[float]) -> list[float]:
    if not returns:
        return []
    var = returns[0] ** 2
    out: list[float] = []
    for r in returns:
        var = _EWMA_LAMBDA * var + (1.0 - _EWMA_LAMBDA) * r * r
        out.append(math.sqrt(max(var, 1e-12)))
    return out


def sample_annual_vol(returns: list[float]) -> float:
    """Independent oracle — annualized sample vol (ST2)."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    return math.sqrt(var) * math.sqrt(_TRADING_DAYS)


def lag1_autocorrelation(returns: list[float]) -> float:
    """Independent oracle — lag-1 autocorrelation (ST2)."""
    n = len(returns)
    if n < 3:
        return 0.0
    xs = returns[1:]
    ys = returns[:-1]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0.0 or den_y == 0.0:
        return 0.0
    rho = num / (den_x * den_y)
    return max(-1.0, min(1.0, rho))


def excess_kurtosis(returns: list[float]) -> float:
    """Independent oracle — excess kurtosis (ST2)."""
    n = len(returns)
    if n < 4:
        return 0.0
    mean = sum(returns) / n
    m2 = sum((r - mean) ** 2 for r in returns) / n
    if m2 == 0.0:
        return 0.0
    m4 = sum((r - mean) ** 4 for r in returns) / n
    return m4 / (m2 * m2) - 3.0


def vol_clustering_ratio(returns: list[float]) -> float:
    """EWMA-vol persistence — order-dependent clustering proxy (ST2)."""
    vols = _ewma_vol_series(returns)
    return abs(lag1_autocorrelation(vols))


def vol_persistence_score(returns: list[float]) -> float:
    """Alias for null-baseline comparisons — serial vol persistence."""
    return vol_clustering_ratio(returns)


def stress_binding_signal(returns: list[float]) -> float:
    """Order-dependent stress metric — serial return + vol persistence."""
    return abs(lag1_autocorrelation(returns)) + vol_persistence_score(returns)


def generate_daily_paths(
    *,
    seed: int,
    n_days: int,
    targets: PathTargets,
) -> list[float]:
    """Emit GARCH/AR(1) daily returns calibrated toward ``targets``."""
    if n_days < 1:
        raise ValueError("n_days must be >= 1")
    if targets.annual_vol < 0:
        raise ValueError("annual_vol must be non-negative")

    rng = random.Random(seed)
    daily_target = _daily_sigma(targets.annual_vol)
    phi = max(-0.95, min(0.95, targets.lag1_autocorr))
    alpha = 0.06
    beta = 0.90
    omega = (daily_target**2) * max(1e-8, 1.0 - alpha - beta)

    returns: list[float] = []
    h = omega / max(1e-8, 1.0 - beta)
    prev_r = 0.0
    k_scale = 1.0 + max(0.0, targets.excess_kurtosis) * 0.08

    for _ in range(n_days):
        z = rng.gauss(0.0, 1.0)
        if abs(z) > 1.2:
            z *= k_scale
        h = omega + alpha * (prev_r**2) + beta * h
        sigma = math.sqrt(max(h, 1e-12))
        r = phi * prev_r + sigma * z
        returns.append(r)
        prev_r = r

    if targets.annual_vol == 0.0:
        return [0.0] * n_days

    realized = sample_annual_vol(returns)
    if realized > 0:
        scale = targets.annual_vol / realized
        returns = [r * scale for r in returns]

    return returns


def shuffle_null(paths: list[float], *, seed: int) -> list[float]:
    """Destroy serial structure — permutation null (ST1 falsifier)."""
    rng = random.Random(seed)
    out = list(paths)
    rng.shuffle(out)
    return out


def bootstrap_null(
    paths: list[float], *, seed: int, n_days: int
) -> list[float]:
    """IID resample null — marginal preserved, dependence destroyed."""
    if n_days < 1:
        raise ValueError("n_days must be >= 1")
    if not paths:
        return []
    rng = random.Random(seed)
    return [paths[rng.randrange(len(paths))] for _ in range(n_days)]
