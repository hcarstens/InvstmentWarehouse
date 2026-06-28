"""pa2 — non-performing-asset (NPA) flag falsifiers (§5 acceptance, §6/§7).

Covers each reason-coded rule (sustained drawdown, stale alt mark, missed
capital call, IPS liquidity breach), walk-forward safety, purity (alerts only,
never staged trades / optimizer mutation), and the dashboard panel.
"""

from __future__ import annotations

import inspect
from datetime import date, timedelta
from decimal import Decimal

import pytest

from warehouse.dashboard.npa_data import load_npa_dashboard
from warehouse.dashboard.render_analyst import render_npa_section
from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.analyst import (
    NpaError,
    NpaFlag,
    NpaReason,
    NpaSubject,
    flag_non_performing,
)
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.research.synthetic import emit_synthetic_household
from warehouse.research.synthetic.fixture_views import (
    lot_positions_from_fixture,
    smoke_as_of_date,
)
from warehouse.research.synthetic.models import (
    SyntheticAltCall,
    SyntheticAltHolding,
)

AS_OF = date(2026, 6, 28)
CONFIG_VERSION = "2026.06"
STALE_DAYS = 180
DRAWDOWN = Decimal("-0.10")
SUSTAINED = Decimal("1.0")


def _lot(
    *,
    lot_id: str = "lot",
    ticker: str = "AAPL",
    asset_class: SecClass = SecClass.EQUITY,
    acq: date = AS_OF - timedelta(days=800),
    cost: Decimal = Decimal("100"),
    mv: Decimal = Decimal("100"),
    liquidity_tier: int = 1,
) -> LotPositionView:
    return LotPositionView(
        lot_id=lot_id,
        account_id="acct",
        account_name="Account",
        security_id=ticker,
        ticker=ticker,
        security_name="Test",
        security_asset_class=asset_class,
        liquidity_tier=liquidity_tier,
        quantity=Decimal("1"),
        cost_basis_per_share=cost,
        total_cost_basis=cost,
        market_price=mv,
        market_value=mv,
        unrealized_gain=mv - cost,
        acquisition_date=acq,
        is_restricted=False,
        wash_sale_substitute_group=None,
    )


def _alt(
    *,
    holding_id: str = "pe-1",
    last_mark: date = AS_OF - timedelta(days=30),
    unfunded: Decimal = Decimal("0"),
    calls: list[SyntheticAltCall] | None = None,
) -> SyntheticAltHolding:
    return SyntheticAltHolding(
        holding_id=holding_id,
        household_id="hh",
        entity_id="ent",
        name="PE Fund",
        asset_type="private_equity",
        committed_capital=Decimal("1000"),
        called_capital=Decimal("800"),
        unfunded_capital=unfunded,
        current_nav=Decimal("800"),
        last_mark_date=last_mark,
        scheduled_calls=calls or [],
    )


def _flag(positions, alts, ips=None) -> list[NpaFlag]:
    return flag_non_performing(
        positions,
        alts,
        ips,
        household_id="hh",
        as_of=AS_OF,
        config_version=CONFIG_VERSION,
        stale_mark_days=STALE_DAYS,
        drawdown_pct=DRAWDOWN,
        sustained_years=SUSTAINED,
    ).flags


# --- (a) sustained drawdown vs cost -----------------------------------------


def test_sustained_drawdown_flag() -> None:
    """Below cost past the threshold *and* the sustained window → flag."""
    lot = _lot(cost=Decimal("100"), mv=Decimal("80"))  # -0.20, held >2y
    flags = _flag([lot], [])
    assert [f.reason for f in flags] == [NpaReason.SUSTAINED_DRAWDOWN]
    assert flags[0].subject == NpaSubject.POSITION
    assert flags[0].observed == Decimal("-0.2000")


def test_drawdown_within_threshold_no_flag() -> None:
    lot = _lot(cost=Decimal("100"), mv=Decimal("95"))  # -0.05, above floor
    assert _flag([lot], []) == []


def test_fresh_drawdown_below_window_no_flag() -> None:
    """A deep dip held under the sustained window is not yet flagged."""
    fresh = _lot(
        cost=Decimal("100"),
        mv=Decimal("70"),
        acq=AS_OF - timedelta(days=90),  # < 1.0y
    )
    assert _flag([fresh], []) == []


# --- (b) stale alt mark ------------------------------------------------------


def test_stale_alt_mark_flag() -> None:
    alt = _alt(last_mark=AS_OF - timedelta(days=STALE_DAYS + 1))
    flags = _flag([], [alt])
    assert [f.reason for f in flags] == [NpaReason.STALE_ALT_MARK]
    assert flags[0].subject == NpaSubject.ALTERNATIVE
    assert flags[0].observed == Decimal(STALE_DAYS + 1)


def test_fresh_alt_mark_no_flag() -> None:
    alt = _alt(last_mark=AS_OF - timedelta(days=STALE_DAYS - 1))
    assert _flag([], [alt]) == []


# --- (c) missed capital call -------------------------------------------------


def test_missed_capital_call_flag() -> None:
    call = SyntheticAltCall(
        event_id="c1",
        holding_id="pe-1",
        event_date=AS_OF - timedelta(days=10),
        amount=Decimal("100"),
    )
    alt = _alt(unfunded=Decimal("200"), calls=[call])
    flags = _flag([], [alt])
    assert NpaReason.MISSED_CAPITAL_CALL in [f.reason for f in flags]
    missed = next(
        f for f in flags if f.reason == NpaReason.MISSED_CAPITAL_CALL
    )
    assert missed.observed == Decimal("200")


def test_future_call_not_missed() -> None:
    call = SyntheticAltCall(
        event_id="c1",
        holding_id="pe-1",
        event_date=AS_OF + timedelta(days=10),
        amount=Decimal("100"),
    )
    alt = _alt(unfunded=Decimal("200"), calls=[call])
    assert _flag([], [alt]) == []


def test_due_call_fully_funded_no_flag() -> None:
    """A past-due call with nothing unfunded is not missed."""
    call = SyntheticAltCall(
        event_id="c1",
        holding_id="pe-1",
        event_date=AS_OF - timedelta(days=10),
        amount=Decimal("100"),
    )
    alt = _alt(unfunded=Decimal("0"), calls=[call])
    assert _flag([], [alt]) == []


# --- (d) IPS liquidity breach ------------------------------------------------


def _ips(floor: Decimal | None) -> InvestmentPolicyStatement:
    return InvestmentPolicyStatement(
        ips_id="ips_1",
        household_id="hh",
        version=1,
        effective_date="2024-01-01",
        allocation_targets=[
            AllocationTarget(
                asset_class=IpsSleeve.EQUITY,
                min_weight=Decimal("0"),
                max_weight=Decimal("1"),
                target_weight=Decimal("1"),
            )
        ],
        liquidity_tier_min_pct=floor,
    )


def test_ips_liquidity_breach_flag() -> None:
    """Illiquid book below the IPS floor → a manifest-level flag."""
    illiquid = _lot(lot_id="alt", liquidity_tier=5, mv=Decimal("900"))
    liquid = _lot(lot_id="cash", liquidity_tier=1, mv=Decimal("100"))
    flags = _flag([illiquid, liquid], [], _ips(Decimal("0.50")))
    breach = [f for f in flags if f.reason == NpaReason.IPS_LIQUIDITY_BREACH]
    assert len(breach) == 1
    assert breach[0].subject == NpaSubject.MANIFEST


def test_ips_liquidity_within_floor_no_flag() -> None:
    liquid = _lot(lot_id="cash", liquidity_tier=1, mv=Decimal("1000"))
    flags = _flag([liquid], [], _ips(Decimal("0.50")))
    assert not any(f.reason == NpaReason.IPS_LIQUIDITY_BREACH for f in flags)


def test_no_ips_floor_no_liquidity_flag() -> None:
    illiquid = _lot(lot_id="alt", liquidity_tier=5, mv=Decimal("900"))
    flags = _flag([illiquid], [], _ips(None))
    assert flags == []


# --- walk-forward safety -----------------------------------------------------


def test_future_acquisition_raises() -> None:
    future = _lot(acq=AS_OF + timedelta(days=1))
    with pytest.raises(NpaError, match="walk-forward"):
        _flag([future], [])


def test_future_mark_raises() -> None:
    alt = _alt(last_mark=AS_OF + timedelta(days=1))
    with pytest.raises(NpaError, match="walk-forward"):
        _flag([], [alt])


# --- purity: alerts only, never an optimizer mutation / staged trade ---------


def test_npa_no_persist() -> None:
    """flag_non_performing is pure: no session, alerts only, deterministic."""
    params = inspect.signature(flag_non_performing).parameters
    assert "ctx" not in params and "session" not in params
    lot = _lot(cost=Decimal("100"), mv=Decimal("80"))
    alt = _alt(last_mark=AS_OF - timedelta(days=STALE_DAYS + 5))
    first = _flag([lot], [alt])
    second = _flag([lot], [alt])
    # Pure: same inputs → same flags; results are alerts, never orders.
    assert first == second
    assert all(isinstance(f, NpaFlag) for f in first)


def test_flags_ordered_deterministically() -> None:
    a = _lot(lot_id="b", cost=Decimal("100"), mv=Decimal("80"))
    b = _lot(lot_id="a", cost=Decimal("100"), mv=Decimal("70"))
    flags = _flag([a, b], [])
    # Sorted by (reason, subject_id) → lot "a" precedes lot "b".
    assert [f.subject_id for f in flags] == ["a", "b"]


# --- §9 fixture flow: founder_executive trips drawdown + stale + missed ------


def test_founder_executive_flow_flags() -> None:
    bundle = emit_synthetic_household(
        cohort_id="founder_executive", seed=11, rung=4, validate=False
    )
    fixture = bundle.fixture
    as_of = smoke_as_of_date(fixture)
    positions = lot_positions_from_fixture(fixture)
    result = flag_non_performing(
        positions,
        fixture.alternative_holdings,
        bundle.ips,
        household_id=fixture.household_id,
        as_of=as_of,
        config_version=CONFIG_VERSION,
        stale_mark_days=STALE_DAYS,
        drawdown_pct=DRAWDOWN,
        sustained_years=SUSTAINED,
    )
    reasons = {f.reason for f in result.flags}
    assert NpaReason.SUSTAINED_DRAWDOWN in reasons
    assert NpaReason.STALE_ALT_MARK in reasons
    assert NpaReason.MISSED_CAPITAL_CALL in reasons
    assert all(isinstance(f, NpaFlag) for f in result.flags)


# --- dashboard panel ---------------------------------------------------------


def test_npa_panel_renders_flags() -> None:
    data = load_npa_dashboard()
    assert data.error is None
    assert data.flags
    html = render_npa_section(data)
    assert "Non-performing-asset flags" in html
    assert "Advisory only" in html
    assert data.flags[0].label in html
