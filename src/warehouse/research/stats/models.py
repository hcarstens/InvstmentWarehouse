"""Daily-statistics records (pv2) — frozen + registered from day one.

The portfolio-side daily stats FIIJ does not compute per book: our own
returns, EWMA conditional vol, a rolling-correlation-shift note (¬PS2 watch),
z-score move significance (signal vs noise — ℍ_PortfolioAnalyst axiom 1), and
position P&L attribution.

Honesty rule (¬Composite Sufficiency): the beta-stripped **factor /
idiosyncratic** leg of the attribution is ``not_computed`` — the daily-window
``PositionAttribution`` rows carry ``active_annualized = None`` (a one-day
window is far below the annualization floor; annualizing it would amplify
noise), never a fake zero. Both ``DailyMove`` and ``DailyStatsReport`` are
``frozen=True`` and registered in ``FROZEN_TYPES`` (the M1/M2 discipline).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from warehouse.decision.analyst.models import PositionAttribution


class PriceObservation(BaseModel):
    """One dated mark for a security — the stats engine's series input.

    Not frozen: this is a transport DTO for the price/mark history series, not
    an audit/replay snapshot (the snapshot is ``DailyStatsReport``).
    """

    security_id: str
    as_of_date: date
    price: Decimal


class DailyMove(BaseModel):
    """A single security's daily move + its significance vs the conditional
    distribution.

    ``zscore`` = the latest return over the EWMA **conditional** vol built from
    the PRIOR returns (not including today), so a move is scored against the
    distribution that preceded it. ``significant`` is ``|zscore|`` past the
    pinned threshold — signal, not noise.
    """

    model_config = ConfigDict(frozen=True)

    security_id: str
    as_of_date: date
    ret: Decimal
    ewma_vol: Decimal
    zscore: Decimal
    significant: bool


class DailyStatsReport(BaseModel):
    """The book's daily-statistics snapshot — audit/replay-critical, immutable.

    ``rolling_corr_note`` summarizes the pairwise-correlation shift (¬PS2:
    correlations are regime-dependent). ``attribution`` reuses the frozen
    ``PositionAttribution`` record; its factor/idiosyncratic leg is
    ``not_computed`` (rows carry ``active_annualized = None``) — never a fake
    zero (¬Composite Sufficiency).
    """

    model_config = ConfigDict(frozen=True)

    as_of_date: date
    stats_config_version: str
    moves: tuple[DailyMove, ...]
    rolling_corr_note: str
    attribution: tuple[PositionAttribution, ...]
    # Surfaced, not hidden (dashboard-first): securities/positions that could
    # not be scored (too few observations) — an honest coverage gap, not a
    # silent omission.
    limitations: tuple[str, ...] = ()
