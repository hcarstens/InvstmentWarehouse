"""qa6 — explicit WalkForwardError expansion (ST2 / H9).

Future-data injection (lots, marks, scenario observations, path slices)
must raise — never clip or default quietly (¬QA6: coverage ≠ checking).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from warehouse.data.ledger.views import LotPositionView, list_lot_positions
from warehouse.data.security_master import AssetClass as SecurityAssetClass
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.models import LotRow, MarketPriceRow
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.research.backtest import WalkForwardError
from warehouse.research.backtest.harness import run_backtest
from warehouse.research.backtest.walk_forward import (
    assert_lots_not_after,
    assert_mark_dates_not_after,
    assert_min_backtest_window,
    assert_scenario_observations_not_after,
    assert_series_cutoff,
)


def _lot_view(
    *,
    lot_id: str = "lot_future",
    acquired: date,
) -> LotPositionView:
    return LotPositionView(
        lot_id=lot_id,
        account_id="acct_taxable",
        account_name="Taxable",
        security_id="sec_vti",
        ticker="VTI",
        security_name="VTI",
        security_asset_class=SecurityAssetClass.ETF,
        liquidity_tier=1,
        quantity=Decimal("10"),
        cost_basis_per_share=Decimal("100"),
        total_cost_basis=Decimal("1000"),
        market_price=Decimal("110"),
        market_value=Decimal("1100"),
        unrealized_gain=Decimal("100"),
        acquisition_date=acquired,
        is_restricted=False,
        wash_sale_substitute_group="us_equity_broad",
    )


# --- unit oracles on guard primitives ----------------------------------------


def test_min_window_below_purge_raises() -> None:
    """Oracle: 4d window < 5d purge → WalkForwardError."""
    with pytest.raises(WalkForwardError, match="4d < 5d purge min"):
        assert_min_backtest_window(
            date(2026, 6, 20),
            date(2026, 6, 24),
            purge_days=5,
        )


def test_future_lot_after_as_of_raises() -> None:
    """qa6 — lot acquired after evaluation cutoff is future data."""
    as_of = date(2026, 6, 24)
    future_lot = _lot_view(acquired=date(2026, 6, 25))
    with pytest.raises(WalkForwardError, match="lot_future"):
        assert_lots_not_after([future_lot], as_of=as_of)


def test_future_mark_after_as_of_raises() -> None:
    """qa6 — mark dated after evaluation cutoff is future data."""
    as_of = date(2026, 6, 24)
    with pytest.raises(WalkForwardError, match="mark as_of_date"):
        assert_mark_dates_not_after([date(2026, 6, 27)], as_of=as_of)


def test_scenario_observation_in_purge_window_raises() -> None:
    """H9 — scenario row dated after as_of inside purge window raises."""
    as_of = date(2026, 6, 24)
    future_obs = (date(2026, 6, 26), "stress_shock")
    with pytest.raises(WalkForwardError, match="stress_shock"):
        assert_scenario_observations_not_after([future_obs], as_of=as_of)


def test_series_cutoff_beyond_walk_forward_raises() -> None:
    """qa6 — path slice past allowed index is a walk-forward violation."""
    with pytest.raises(WalkForwardError, match="end_index 120"):
        assert_series_cutoff(
            end_index=120,
            cutoff_index=100,
            label="daily_paths",
        )


# --- harness integration (future-data injection) -----------------------------


def test_backtest_short_window_raises() -> None:
    """Existing guard — window shorter than purge min."""
    bootstrap_database(seed=True)
    with session_scope() as session:
        with pytest.raises(WalkForwardError, match="purge min"):
            run_backtest(
                session,
                DEMO_HOUSEHOLD_ID,
                start_date=date(2026, 6, 20),
                end_date=date(2026, 6, 24),
            )


def test_backtest_future_lot_injection_raises() -> None:
    """qa6 — lot acquired after end_date blocks the backtest."""
    bootstrap_database(seed=True)
    with session_scope() as session:
        lot = session.get(LotRow, "lot_vti_1")
        assert lot is not None
        original_acq = lot.acquisition_date
        lot.acquisition_date = date(2026, 6, 25)
        session.flush()
        try:
            with pytest.raises(WalkForwardError, match="lot_vti_1"):
                run_backtest(
                    session,
                    DEMO_HOUSEHOLD_ID,
                    start_date=date(2024, 1, 1),
                    end_date=date(2026, 6, 24),
                )
        finally:
            lot.acquisition_date = original_acq
            session.flush()


def test_backtest_future_mark_injection_raises() -> None:
    """qa6 — mark as_of_date after end_date blocks the backtest."""
    bootstrap_database(seed=True)
    with session_scope() as session:
        stale = session.get(LotRow, "lot_qa6_future")
        if stale is not None:
            session.delete(stale)
        mark = session.get(MarketPriceRow, "sec_vti")
        assert mark is not None
        original_as_of = mark.as_of_date
        mark.as_of_date = date(2026, 6, 30)
        session.flush()
        try:
            with pytest.raises(WalkForwardError, match="mark as_of_date"):
                run_backtest(
                    session,
                    DEMO_HOUSEHOLD_ID,
                    start_date=date(2024, 1, 1),
                    end_date=date(2026, 6, 24),
                )
        finally:
            mark.as_of_date = original_as_of
            session.flush()


def test_backtest_clean_seed_passes_walk_forward() -> None:
    """Green path — demo seed has no future lots or marks."""
    bootstrap_database(seed=True)
    with session_scope() as session:
        lot = session.get(LotRow, "lot_vti_1")
        if lot is not None and lot.acquisition_date > date(2026, 6, 24):
            lot.acquisition_date = date(2023, 4, 10)
            session.flush()
        positions = list_lot_positions(session, household_id=DEMO_HOUSEHOLD_ID)
        assert positions
        result = run_backtest(
            session,
            DEMO_HOUSEHOLD_ID,
            start_date=date(2024, 1, 1),
            end_date=date(2026, 6, 24),
        )
    assert result.run_id.startswith("bt_")
