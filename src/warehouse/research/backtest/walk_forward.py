"""Walk-forward guards — explicit purge + future-data checks (qa6).

Coverage measures execution, not checking (¬QA6). These guards raise
``WalkForwardError`` when injected marks, lots, or scenario observations
would peek past the evaluation cutoff — never clip or default quietly.

Wiring status (a defined guard must imply a called guard):

- ``assert_min_backtest_window``, ``assert_lots_not_after``, and
  ``assert_mark_dates_not_after`` are WIRED into the live backtest path via
  ``validate_backtest_walk_forward`` (called from ``harness.run_backtest``).
- ``assert_scenario_observations_not_after`` and ``assert_series_cutoff`` are
  now WIRED on the pm_pivot pv2 daily-loop time series (review M3 closed —
  first real series):
  * ``assert_scenario_observations_not_after`` guards the FIIJ finance-view
    snapshot dates in ``warehouse.data.ingest.fiij.load_fiij_snapshot`` — a
    snapshot dated after ``as_of`` raises ``WalkForwardError``.
  * ``assert_series_cutoff`` guards the price/mark series in
    ``warehouse.research.stats.stats_daily`` — an observation dated after
    ``as_of`` raises ``WalkForwardError``.
  Both remain pinned by direct falsifier tests in
  ``tests/test_walk_forward_guard.py`` in addition to the live call sites.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.data.ledger.views import LotPositionView
from warehouse.infra.db.models import MarketPriceRow
from warehouse.research.backtest import WalkForwardError


def assert_min_backtest_window(
    start_date: date,
    end_date: date,
    *,
    purge_days: int,
) -> None:
    """Require backtest window length ≥ configured purge days."""
    window_days = (end_date - start_date).days
    if window_days < purge_days:
        raise WalkForwardError(f"{window_days}d < {purge_days}d purge min")


def assert_lots_not_after(
    positions: Sequence[LotPositionView],
    *,
    as_of: date,
) -> None:
    """Reject lots acquired after the walk-forward cutoff."""
    for pos in positions:
        if pos.acquisition_date > as_of:
            raise WalkForwardError(
                f"lot {pos.lot_id} acquired {pos.acquisition_date} "
                f"after as_of {as_of}"
            )


def assert_mark_dates_not_after(
    mark_dates: Iterable[date],
    *,
    as_of: date,
) -> None:
    """Reject price marks dated after the evaluation cutoff."""
    for mark_date in mark_dates:
        if mark_date > as_of:
            raise WalkForwardError(
                f"mark as_of_date {mark_date} after evaluation end {as_of}"
            )


def assert_scenario_observations_not_after(
    observations: Iterable[tuple[date, str]],
    *,
    as_of: date,
) -> None:
    """Reject dated scenario rows that peek past the walk-forward cutoff.

    Forward-provisioned: not yet wired into a live backtest leg (no scenario
    series input exists). Pinned by a direct falsifier test. See module note.
    """
    for obs_date, label in observations:
        if obs_date > as_of:
            raise WalkForwardError(
                f"{label} observation {obs_date} after as_of {as_of}"
            )


def assert_series_cutoff(
    *,
    end_index: int,
    cutoff_index: int,
    label: str = "series",
) -> None:
    """Reject path slices beyond the allowed walk-forward index.

    Forward-provisioned: not yet wired into a live backtest leg (no path-slice
    input exists). Pinned by a direct falsifier test. See module note.
    """
    if end_index > cutoff_index:
        raise WalkForwardError(
            f"{label} end_index {end_index} exceeds walk-forward "
            f"cutoff {cutoff_index}"
        )


def mark_dates_for_positions(
    session: Session,
    positions: Sequence[LotPositionView],
) -> list[date]:
    """Load ``as_of_date`` for each held security — empty when no positions."""
    security_ids = {pos.security_id for pos in positions}
    if not security_ids:
        return []
    return list(
        session.scalars(
            select(MarketPriceRow.as_of_date).where(
                MarketPriceRow.security_id.in_(security_ids)
            )
        ).all()
    )


def validate_backtest_walk_forward(
    session: Session,
    *,
    household_id: str,
    positions: Sequence[LotPositionView],
    start_date: date,
    end_date: date,
    purge_days: int,
) -> None:
    """Run all walk-forward guards before a backtest computes returns."""
    _ = household_id  # reserved for household-scoped mark queries later
    assert_min_backtest_window(start_date, end_date, purge_days=purge_days)
    assert_lots_not_after(positions, as_of=end_date)
    assert_mark_dates_not_after(
        mark_dates_for_positions(session, positions),
        as_of=end_date,
    )
