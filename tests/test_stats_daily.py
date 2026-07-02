"""Daily statistics engine (pv2) — z-scores, significance, guard, factor.

Falsifiers: a synthetic ~3σ move flags ``significant=True`` while a flat series
flags none; a mark dated after ``as_of`` RAISES ``WalkForwardError`` (the M3
``assert_series_cutoff`` guard is now live); factor attribution rows render
``not_computed`` (``active_annualized is None``), never a fake zero; and
``stats.daily`` is pure (a poisoned session is never touched).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

import warehouse.messaging.handlers  # noqa: F401 — register ops
from warehouse.decision.pm import build_working_set_from_bundle
from warehouse.messaging import (
    REGISTRY,
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
)
from warehouse.messaging.payloads import StatsDailyPayload
from warehouse.research.backtest import WalkForwardError
from warehouse.research.stats import (
    DailyStatsReport,
    PriceObservation,
    stats_daily,
)
from warehouse.research.synthetic import emit_synthetic_household

_AS_OF = date(2026, 6, 30)


def _book():  # type: ignore[no-untyped-def]
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    return build_working_set_from_bundle(bundle)


def _series(
    security_id: str, prices: list[str], *, end: date = _AS_OF
) -> list[PriceObservation]:
    start = end - timedelta(days=len(prices) - 1)
    return [
        PriceObservation(
            security_id=security_id,
            as_of_date=start + timedelta(days=i),
            price=Decimal(p),
        )
        for i, p in enumerate(prices)
    ]


def test_three_sigma_move_is_significant_flat_is_not() -> None:
    spike = _series(
        "SEC_SPIKE",
        ["100", "100.5", "99.8", "100.3", "100.1", "100.2", "100.0", "115.0"],
    )
    flat = _series(
        "SEC_FLAT", ["50", "50", "50", "50", "50", "50", "50", "50"]
    )
    report = stats_daily(_book(), _AS_OF, spike + flat)
    by_sec = {m.security_id: m for m in report.moves}
    assert by_sec["SEC_SPIKE"].significant is True
    assert abs(by_sec["SEC_SPIKE"].zscore) > Decimal("3")
    assert by_sec["SEC_FLAT"].significant is False
    assert by_sec["SEC_FLAT"].zscore == Decimal("0")


def test_factor_attribution_renders_not_computed() -> None:
    book = _book()
    # Seed a series for every security the book holds so attribution is scored.
    history: list[PriceObservation] = []
    for i, sec in enumerate({p.security_id for p in book.positions}):
        base = 100 + i
        history += _series(
            sec, [str(base), str(base + 1), str(base + 2), str(base + 1)]
        )
    report = stats_daily(book, _AS_OF, history)
    assert report.attribution, "expected scored positions"
    # The factor/idiosyncratic leg is not_computed — never a fake zero.
    assert all(a.active_annualized is None for a in report.attribution)


def test_series_cutoff_wired_raises_on_future_mark() -> None:
    future = _series(
        "SEC_FUT", ["100", "101", "102"], end=_AS_OF + timedelta(days=1)
    )
    with pytest.raises(WalkForwardError):
        stats_daily(_book(), _AS_OF, future)


def test_stats_daily_pure_via_dispatch() -> None:
    book = _book()
    history = _series("SEC_X", ["100", "101", "100.5", "101.2"])
    ctx = DispatchContext(session=_Poison())  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="stats.daily",
            kind=Kind.EVALUATE,
            payload=StatsDailyPayload(
                book=book, price_history=tuple(history), as_of_date=_AS_OF
            ),
            correlation_id="stats-trace",
            household_id=book.household_id,
        ),
    )
    assert isinstance(out, DailyStatsReport)
    assert out.moves


def test_stats_is_new_op_pm_surface_unchanged() -> None:
    stats_ops = {op for op in REGISTRY if op.startswith("stats.")}
    assert stats_ops == {"stats.daily"}
    pm_ops = {op for op in REGISTRY if op.startswith("pm.")}
    assert pm_ops == {"pm.advise"}


class _Poison:
    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"stats.daily touched session.{name}")
