"""ST1 + ST2 null-baseline falsifiers for structured daily paths (st5g).

Shuffle and bootstrap nulls deliberately destroy serial structure; the
structured generator must retain more stress-binding signal (SDG3 lens).
"""

from __future__ import annotations

from tests.synth_stats_helpers import DEFAULT_N_DAYS, MAX_BOOTSTRAP_DRAWS
from warehouse.research.synthetic.daily_paths import (
    DEFAULT_TARGETS,
    bootstrap_null,
    generate_daily_paths,
    shuffle_null,
    vol_persistence_score,
)


def _structured_paths() -> list[float]:
    return generate_daily_paths(
        seed=42, n_days=DEFAULT_N_DAYS, targets=DEFAULT_TARGETS
    )


def test_structured_beats_shuffle_null_on_stress_signal() -> None:
    structured = _structured_paths()
    shuffled = shuffle_null(structured, seed=11)
    assert vol_persistence_score(structured) > vol_persistence_score(shuffled)


def test_structured_beats_bootstrap_null_on_stress_signal() -> None:
    structured = _structured_paths()
    boot = bootstrap_null(structured, seed=42, n_days=DEFAULT_N_DAYS)
    assert vol_persistence_score(structured) > vol_persistence_score(boot)


def test_nulls_strictly_worse_not_equal_across_bootstrap_draws() -> None:
    structured = _structured_paths()
    base_signal = vol_persistence_score(structured)
    worse_count = 0
    for draw in range(MAX_BOOTSTRAP_DRAWS):
        boot = bootstrap_null(
            structured, seed=1000 + draw, n_days=DEFAULT_N_DAYS
        )
        if vol_persistence_score(boot) < base_signal:
            worse_count += 1
    assert worse_count >= MAX_BOOTSTRAP_DRAWS // 2
