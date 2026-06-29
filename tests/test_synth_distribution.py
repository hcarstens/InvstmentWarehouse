"""ST6 + ST2 + SDG1 distributional validation of synthetic daily paths (st5g).

Independent sample-stat oracles — never compare generator output to itself.
"""

from __future__ import annotations

import pytest

from tests.synth_stats_helpers import (
    AUTOCORR_TOL,
    CLUSTER_TOL,
    DEFAULT_N_DAYS,
    KURTOSIS_TOL,
    VOL_TOL,
    oracle_annual_vol,
    oracle_excess_kurtosis,
    oracle_lag1_autocorr,
    oracle_vol_clustering,
)
from warehouse.research.synthetic.cohort import (
    AXIOM_SET_HASH,
    GENERATOR_VERSION,
)
from warehouse.research.synthetic.daily_paths import (
    DEFAULT_TARGETS,
    generate_daily_paths,
)
from warehouse.research.synthetic.daily_paths import (
    GENERATOR_VERSION as PATH_GENERATOR_VERSION,
)


def test_sample_vol_non_negative_and_within_tolerance() -> None:
    paths = generate_daily_paths(
        seed=42, n_days=DEFAULT_N_DAYS, targets=DEFAULT_TARGETS
    )
    vol = oracle_annual_vol(paths)
    assert vol >= 0.0
    assert vol == pytest.approx(DEFAULT_TARGETS.annual_vol, abs=VOL_TOL)


def test_lag1_autocorr_bounded_and_near_target() -> None:
    paths = generate_daily_paths(
        seed=11, n_days=DEFAULT_N_DAYS, targets=DEFAULT_TARGETS
    )
    ac = oracle_lag1_autocorr(paths)
    assert abs(ac) <= 1.0
    assert ac == pytest.approx(DEFAULT_TARGETS.lag1_autocorr, abs=AUTOCORR_TOL)


def test_excess_kurtosis_and_vol_clustering_within_tolerance() -> None:
    paths = generate_daily_paths(
        seed=99, n_days=DEFAULT_N_DAYS, targets=DEFAULT_TARGETS
    )
    ek = oracle_excess_kurtosis(paths)
    vc = oracle_vol_clustering(paths)
    assert ek == pytest.approx(
        DEFAULT_TARGETS.excess_kurtosis, abs=KURTOSIS_TOL
    )
    assert vc == pytest.approx(DEFAULT_TARGETS.vol_clustering, abs=CLUSTER_TOL)


def test_same_seed_deterministic_and_provenance_pinned() -> None:
    first = generate_daily_paths(
        seed=42, n_days=DEFAULT_N_DAYS, targets=DEFAULT_TARGETS
    )
    second = generate_daily_paths(
        seed=42, n_days=DEFAULT_N_DAYS, targets=DEFAULT_TARGETS
    )
    assert first == second
    assert PATH_GENERATOR_VERSION == "2026.06"
    assert GENERATOR_VERSION == "2026.03"
    assert AXIOM_SET_HASH == "hnw-sdg-v1"


def test_boundary_n_days_one_and_zero_vol_target() -> None:
    one_day = generate_daily_paths(seed=42, n_days=1, targets=DEFAULT_TARGETS)
    assert len(one_day) == 1
    assert oracle_annual_vol(one_day) >= 0.0

    from warehouse.research.synthetic.daily_paths import PathTargets

    zero_vol = PathTargets(
        annual_vol=0.0,
        lag1_autocorr=0.0,
        excess_kurtosis=0.0,
        vol_clustering=1.0,
    )
    flat = generate_daily_paths(seed=11, n_days=5, targets=zero_vol)
    assert flat == [0.0] * 5


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError, match="n_days"):
        generate_daily_paths(seed=1, n_days=0, targets=DEFAULT_TARGETS)

    from warehouse.research.synthetic.daily_paths import PathTargets

    bad = PathTargets(
        annual_vol=-0.01,
        lag1_autocorr=0.0,
        excess_kurtosis=0.0,
        vol_clustering=1.0,
    )
    with pytest.raises(ValueError, match="annual_vol"):
        generate_daily_paths(seed=1, n_days=10, targets=bad)
