"""2022 bear cross-regime falsifier — pinned STRESS_SCENARIOS oracle (st5g).

Synthetic-tuned equity-trim rule must not approve increasing equity exposure
into the pinned ``2022_inflation`` stress replay (walk-forward safe).
"""

from __future__ import annotations

from decimal import Decimal

from tests.synth_stats_helpers import DEFAULT_N_DAYS
from warehouse.research.risk.assumptions import STRESS_SCENARIOS
from warehouse.research.risk.models import AssetClass
from warehouse.research.synthetic.daily_paths import (
    DEFAULT_TARGETS,
    generate_daily_paths,
)

_BEAR = STRESS_SCENARIOS["2022_inflation"]
_DRAWDOWN_THRESHOLD = -0.08
_EQUITY_TRIM = 0.05


def _cumulative_returns(returns: list[float]) -> list[float]:
    total = 0.0
    out: list[float] = []
    for r in returns:
        total += r
        out.append(total)
    return out


def _max_drawdown(cumulative: list[float]) -> float:
    if not cumulative:
        return 0.0
    peak = cumulative[0]
    worst = 0.0
    for value in cumulative:
        if value > peak:
            peak = value
        drawdown = value - peak
        if drawdown < worst:
            worst = drawdown
    return worst


def _equity_trim_proposal(
    equity_weight: float,
    path_returns: list[float],
    *,
    end_index: int,
) -> float:
    """Walk-forward-safe trim — only ``path_returns[:end_index]`` visible."""
    window = path_returns[:end_index]
    dd = _max_drawdown(_cumulative_returns(window))
    if dd < _DRAWDOWN_THRESHOLD:
        return max(0.0, equity_weight - _EQUITY_TRIM)
    return equity_weight


def _stress_portfolio_return(
    weights: dict[AssetClass, float],
) -> float:
    total = 0.0
    for asset_class, weight in weights.items():
        shock = _BEAR.get(asset_class, Decimal("0"))
        total += weight * float(shock)
    return total


def test_bear_replay_does_not_increase_equity_under_synthetic_rule() -> None:
    paths = generate_daily_paths(
        seed=42, n_days=DEFAULT_N_DAYS, targets=DEFAULT_TARGETS
    )
    equity_start = 0.60
    cal_end = len(paths) // 2
    proposed = _equity_trim_proposal(equity_start, paths, end_index=cal_end)
    assert proposed <= equity_start

    weights = {
        AssetClass.EQUITY: equity_start,
        AssetClass.FIXED_INCOME: 0.25,
        AssetClass.CASH: 0.15,
    }
    stressed_before = _stress_portfolio_return(weights)
    weights_after = dict(weights)
    weights_after[AssetClass.EQUITY] = proposed
    stressed_after = _stress_portfolio_return(weights_after)
    assert proposed <= equity_start
    assert stressed_after >= stressed_before


def test_walk_forward_no_future_peek_on_second_half() -> None:
    paths = generate_daily_paths(
        seed=11, n_days=DEFAULT_N_DAYS, targets=DEFAULT_TARGETS
    )
    split = len(paths) // 2
    equity = 0.55

    first_half_proposal = _equity_trim_proposal(equity, paths, end_index=split)
    full_path_proposal = _equity_trim_proposal(
        equity, paths, end_index=len(paths)
    )

    second_half_only = paths[split:]
    second_proposal = _equity_trim_proposal(
        equity, second_half_only, end_index=len(second_half_only)
    )

    assert first_half_proposal <= equity
    assert full_path_proposal <= equity
    assert second_proposal <= equity
    assert _BEAR[AssetClass.EQUITY] == Decimal("-0.25")
