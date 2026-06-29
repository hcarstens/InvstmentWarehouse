"""Shared tolerances and oracles for st5g statistical synthetic tests (ST2)."""

from __future__ import annotations

from warehouse.research.synthetic.daily_paths import (
    DEFAULT_TARGETS,
    PathTargets,
    excess_kurtosis,
    lag1_autocorrelation,
    sample_annual_vol,
    vol_clustering_ratio,
)

# Independent oracles — re-export for tests (not generator internals).
oracle_annual_vol = sample_annual_vol
oracle_lag1_autocorr = lag1_autocorrelation
oracle_excess_kurtosis = excess_kurtosis
oracle_vol_clustering = vol_clustering_ratio

VOL_TOL = 0.04
AUTOCORR_TOL = 0.12
KURTOSIS_TOL = 2.5
CLUSTER_TOL = 0.05

DEFAULT_N_DAYS = 252
MAX_N_DAYS = 504
MAX_BOOTSTRAP_DRAWS = 100

ABLATON_SEEDS = (11, 42, 99)

__all__ = [
    "ABLATON_SEEDS",
    "AUTOCORR_TOL",
    "CLUSTER_TOL",
    "DEFAULT_N_DAYS",
    "DEFAULT_TARGETS",
    "KURTOSIS_TOL",
    "MAX_BOOTSTRAP_DRAWS",
    "MAX_N_DAYS",
    "VOL_TOL",
    "PathTargets",
    "oracle_annual_vol",
    "oracle_excess_kurtosis",
    "oracle_lag1_autocorr",
    "oracle_vol_clustering",
]
