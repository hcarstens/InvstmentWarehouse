"""Daily statistics engine (pv2) — the portfolio-side stats FIIJ omits.

``stats_daily`` computes, for our own book, the daily returns, EWMA conditional
vol, z-score move significance (signal vs noise — ℍ_PortfolioAnalyst axiom 1),
a rolling-correlation-shift note (¬PS2), and position P&L attribution (the
beta-stripped factor/idiosyncratic leg is ``not_computed``, never a fake zero).

Pure and advisory: it reads the passed book + price history, mutates nothing,
persists nothing (mirrors ``beliefs.update`` / ``pm.advise``).

Walk-forward safe (M3 — first real time series): the price series is guarded by
``assert_series_cutoff`` (a live call site for a previously dead guard) — an
observation dated AFTER ``as_of`` raises ``WalkForwardError``, never a silent
clip. This is one of the two guards pv2 wires; the FIIJ adapter wires the other
(``assert_scenario_observations_not_after``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from typing import TYPE_CHECKING

from warehouse.config import Settings, get_settings
from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.analyst.attribution import risk_class_for
from warehouse.decision.analyst.models import PositionAttribution
from warehouse.decision.ips.rollup import ips_sleeve_for_position
from warehouse.research.backtest.walk_forward import assert_series_cutoff
from warehouse.research.risk.models import AssetClass as RiskClass
from warehouse.research.risk.scenarios import assumptions_for
from warehouse.research.stats.models import (
    DailyMove,
    DailyStatsReport,
    PriceObservation,
)

if TYPE_CHECKING:  # avoid an import cycle with messaging.payloads (Book).
    from warehouse.messaging.payloads import PmAdvisePayload

__all__ = [
    "DailyMove",
    "DailyStatsReport",
    "PriceObservation",
    "stats_daily",
]

_Z_QUANTUM = Decimal("0.0001")
_VOL_QUANTUM = Decimal("0.000001")
_RET_QUANTUM = Decimal("0.000001")
_DAYS_PER_YEAR = Decimal("365.25")


def _q(value: float, quantum: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_EVEN)


def _series_by_security(
    price_history: Sequence[PriceObservation], *, as_of: date
) -> dict[str, list[tuple[date, Decimal]]]:
    """Group + sort marks per security; guard the walk-forward cutoff.

    Raises ``WalkForwardError`` (via ``assert_series_cutoff``) if any mark is
    dated after ``as_of`` — the first LIVE call site for that previously dead
    guard. Never clips a future observation silently.
    """
    all_dates = sorted({obs.as_of_date for obs in price_history})
    if all_dates:
        cutoff_index = -1
        for i, d in enumerate(all_dates):
            if d <= as_of:
                cutoff_index = i
        assert_series_cutoff(
            end_index=len(all_dates) - 1,
            cutoff_index=cutoff_index,
            label="price series",
        )
    by_sec: dict[str, list[tuple[date, Decimal]]] = {}
    for obs in price_history:
        by_sec.setdefault(obs.security_id, []).append(
            (obs.as_of_date, obs.price)
        )
    for series in by_sec.values():
        series.sort(key=lambda row: row[0])
    return by_sec


def _returns(prices: list[Decimal]) -> list[float]:
    out: list[float] = []
    for prev, cur in zip(prices, prices[1:], strict=False):
        if prev == 0:
            continue
        out.append(float(cur / prev) - 1.0)
    return out


def _ewma_vol(returns: list[float], window: int) -> float:
    """EWMA (RiskMetrics span) vol of a return series; 0.0 if empty/flat."""
    if not returns:
        return 0.0
    alpha = 2.0 / (window + 1)
    var = returns[0] ** 2
    for r in returns[1:]:
        var = alpha * (r**2) + (1.0 - alpha) * var
    return math.sqrt(var)


def _realized_vol(returns: list[float]) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / n
    return math.sqrt(var)


def _pairwise_corr(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 2:
        return None
    a, b = a[-n:], b[-n:]
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=False))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        return None
    return cov / math.sqrt(va * vb)


def _corr_note(returns_by_sec: dict[str, list[float]]) -> str:
    """Regime-dependent correlation-shift note (¬PS2 watch).

    Compares average pairwise ρ across the book's securities in a prior vs a
    recent window; stays ``not_computed`` when the sample is too thin to
    license a claim (Bayesian-with-real-priors, not frequentist).
    """
    series = [r for r in returns_by_sec.values() if len(r) >= 4]
    if len(series) < 2:
        return (
            "not_computed — need ≥2 securities with ≥4 overlapping returns "
            "for a correlation-shift read (¬PS2)"
        )
    length = min(len(r) for r in series)
    half = length // 2
    if half < 2:
        return (
            "not_computed — insufficient overlapping history for a "
            "correlation-shift read (¬PS2)"
        )
    prior_pairs: list[float] = []
    recent_pairs: list[float] = []
    for i in range(len(series)):
        for j in range(i + 1, len(series)):
            a, b = series[i][-length:], series[j][-length:]
            cp = _pairwise_corr(a[:half], b[:half])
            cr = _pairwise_corr(a[half:], b[half:])
            if cp is not None:
                prior_pairs.append(cp)
            if cr is not None:
                recent_pairs.append(cr)
    if not prior_pairs or not recent_pairs:
        return (
            "not_computed — degenerate (flat) returns in the window; "
            "no correlation-shift read (¬PS2)"
        )
    prior = sum(prior_pairs) / len(prior_pairs)
    recent = sum(recent_pairs) / len(recent_pairs)
    return (
        f"avg pairwise ρ {prior:+.2f} → {recent:+.2f} "
        f"(Δ {recent - prior:+.2f}); correlations are regime-dependent "
        "(¬PS2 watch) — a spike toward 1 collapses diversification exactly "
        "when it is needed"
    )


def _move_for(
    security_id: str,
    series: list[tuple[date, Decimal]],
    *,
    window: int,
    z_threshold: float,
) -> tuple[DailyMove | None, list[float]]:
    prices = [p for _, p in series]
    returns = _returns(prices)
    if not returns:
        return None, []
    last_ret = returns[-1]
    # Conditional vol from the PRIOR returns — score the move against the
    # distribution that preceded it (not one inflated by the move itself).
    prior = returns[:-1]
    cond_vol = _ewma_vol(prior, window)
    if cond_vol <= 0:
        cond_vol = _realized_vol(returns)
    zscore = last_ret / cond_vol if cond_vol > 0 else 0.0
    move = DailyMove(
        security_id=security_id,
        as_of_date=series[-1][0],
        ret=_q(last_ret, _RET_QUANTUM),
        ewma_vol=_q(cond_vol, _VOL_QUANTUM),
        zscore=_q(zscore, _Z_QUANTUM),
        significant=abs(zscore) > z_threshold,
    )
    return move, returns


def _attribution_row(
    pos: LotPositionView,
    series: list[tuple[date, Decimal]],
    class_expected: dict[RiskClass, Decimal],
) -> PositionAttribution | None:
    first_date, first_price = series[0]
    last_date, last_price = series[-1]
    if first_price <= 0:
        return None
    total_return = last_price / first_price - Decimal("1")
    window_days = max((last_date - first_date).days, 0)
    window_years = Decimal(window_days) / _DAYS_PER_YEAR
    risk_class = risk_class_for(pos.security_asset_class)
    ce = class_expected[risk_class]
    # De-annualize the class assumption onto the (short) window (analyst A.2 —
    # no 1/window explosion). Factor/idiosyncratic leg → not_computed:
    # active_annualized stays None (a daily window is below the annualization
    # floor; annualizing it would amplify noise), never a fake zero.
    expected_cumulative = (ce * window_years).quantize(_RET_QUANTUM)
    market_value = pos.market_value or (pos.quantity * last_price)
    return PositionAttribution(
        lot_id=pos.lot_id,
        account_id=pos.account_id,
        ticker=pos.ticker,
        security_asset_class=pos.security_asset_class,
        risk_class=risk_class,
        liquidity_tier=pos.liquidity_tier,
        holding_years=window_years.quantize(Decimal("0.0001")),
        market_value=market_value,
        total_return=total_return.quantize(_RET_QUANTUM),
        class_expected=ce,
        expected_cumulative=expected_cumulative,
        active_return=(total_return - expected_cumulative).quantize(
            _RET_QUANTUM
        ),
        active_annualized=None,
    )


def stats_daily(
    book: PmAdvisePayload,
    as_of: date,
    price_history: Sequence[PriceObservation],
    *,
    settings: Settings | None = None,
) -> DailyStatsReport:
    """Daily statistics for the book — returns, vol, z-scores, attribution.

    Pure: reads the passed book + ``price_history``, mutates nothing. Raises
    ``WalkForwardError`` if any mark is dated after ``as_of`` (the M3 guard is
    now live). ``significant`` is ``|z|`` past the pinned threshold. The factor
    attribution leg renders ``not_computed`` (``active_annualized = None``).
    """
    cfg = settings or get_settings()
    window = cfg.stats_ewma_window
    z_threshold = cfg.stats_zscore_significant_threshold
    by_sec = _series_by_security(price_history, as_of=as_of)

    moves: list[DailyMove] = []
    returns_by_sec: dict[str, list[float]] = {}
    for security_id, series in sorted(by_sec.items()):
        move, returns = _move_for(
            security_id, series, window=window, z_threshold=z_threshold
        )
        if move is not None:
            moves.append(move)
            returns_by_sec[security_id] = returns

    class_expected = dict(assumptions_for("base").class_expected_return)
    attribution: list[PositionAttribution] = []
    unscored_secs: set[str] = set()
    for pos in book.positions:
        pos_series = by_sec.get(pos.security_id)
        if not pos_series or len(pos_series) < 2:
            unscored_secs.add(pos.security_id)
            continue
        # ips_sleeve_for_position asserts the position maps to a sleeve — a
        # loud failure on an unmappable book, never a silent skip.
        ips_sleeve_for_position(pos)
        row = _attribution_row(pos, pos_series, class_expected)
        if row is not None:
            attribution.append(row)

    limitations: list[str] = []
    if unscored_secs:
        limitations.append(
            f"{len(unscored_secs)} security(ies) with <2 marks not scored "
            "(no return series) — coverage gap surfaced, not hidden"
        )
    limitations.append(
        "factor/idiosyncratic attribution leg not_computed "
        "(no realized class-return series to strip); daily active_annualized "
        "is None, never a fake zero (¬Composite Sufficiency)"
    )

    return DailyStatsReport(
        as_of_date=as_of,
        stats_config_version=cfg.stats_config_version,
        moves=tuple(moves),
        rolling_corr_note=_corr_note(returns_by_sec),
        attribution=tuple(attribution),
        limitations=tuple(limitations),
    )
