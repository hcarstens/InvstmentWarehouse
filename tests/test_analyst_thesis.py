"""pa1 — thesis + kill-criteria falsifiers (§5 acceptance, §6/§7).

Covers: kill-criteria breach → ALERT (never a staged trade), pre-committed
(no-hindsight) effective dates, and checkpoint 1 flipping not_documented →
PASS/BREACH once a thesis exists.
"""

from __future__ import annotations

import inspect
from datetime import date, timedelta
from decimal import Decimal

import pytest

from warehouse.dashboard.analyst_data import load_kill_criteria_dashboard
from warehouse.dashboard.render_analyst import render_analyst_section
from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.analyst import (
    AnalystCheckpointScore,
    KillBreach,
    KillCriteria,
    KillCriterion,
    PositionThesis,
    ThesisError,
    ThesisStore,
    evaluate_attribution,
    evaluate_kill_criteria,
    score_analyst_checkpoints,
)
from warehouse.research.risk.scenarios import assumptions_for
from warehouse.research.synthetic import (
    emit_synthetic_household,
    emit_synthetic_theses,
    synthetic_thesis_as_of,
)
from warehouse.research.synthetic.fixture_views import (
    lot_positions_from_fixture,
)

AS_OF = date(2026, 6, 28)
EXPECTED = assumptions_for("base").class_expected_return
_S = AnalystCheckpointScore


def _lot(
    *,
    lot_id: str = "lot",
    account_id: str = "acct",
    ticker: str = "AAPL",
    asset_class: SecClass = SecClass.EQUITY,
    acq: date = AS_OF - timedelta(days=400),
    cost: Decimal = Decimal("100"),
    mv: Decimal = Decimal("100"),
    liquidity_tier: int = 1,
) -> LotPositionView:
    return LotPositionView(
        lot_id=lot_id,
        account_id=account_id,
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


def _thesis(
    *,
    account_id: str = "acct",
    instrument: str = "AAPL",
    effective: date = AS_OF - timedelta(days=500),
    kill: KillCriteria,
) -> PositionThesis:
    return PositionThesis(
        account_id=account_id,
        instrument=instrument,
        mechanism="test thesis",
        effective_date=effective,
        kill_criteria=kill,
        config_version="2026.06",
    )


def _report(positions: list[LotPositionView]):
    return evaluate_attribution(
        positions,
        EXPECTED,
        household_id="hh_test",
        as_of=AS_OF,
        config_version="2026.06",
        min_holding_years=Decimal("0.5"),
    )


# --- §5 acceptance: drawdown kill, alerts only ------------------------------


def test_drawdown_kill_breaches_with_single_alert() -> None:
    """Drawdown kill at −20%, position at −25% → exactly one breach."""
    lot = _lot(cost=Decimal("100"), mv=Decimal("75"))  # total_return −0.25
    thesis = _thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")))
    breaches = evaluate_kill_criteria(lot, thesis, as_of=AS_OF)
    assert len(breaches) == 1
    assert breaches[0].criterion == KillCriterion.DRAWDOWN_VS_COST
    assert breaches[0].observed == Decimal("-0.25")
    assert breaches[0].threshold == Decimal("-0.20")


def test_drawdown_within_floor_no_breach() -> None:
    lot = _lot(cost=Decimal("100"), mv=Decimal("90"))  # −0.10
    thesis = _thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")))
    assert evaluate_kill_criteria(lot, thesis, as_of=AS_OF) == []


def test_kill_criteria_no_persist() -> None:
    """evaluate_kill_criteria is pure: alerts only, no session, no staging."""
    params = inspect.signature(evaluate_kill_criteria).parameters
    assert "ctx" not in params and "session" not in params
    lot = _lot(cost=Decimal("100"), mv=Decimal("70"))
    thesis = _thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")))
    first = evaluate_kill_criteria(lot, thesis, as_of=AS_OF)
    second = evaluate_kill_criteria(lot, thesis, as_of=AS_OF)
    # Pure: same inputs → same alerts; results are alerts, never orders.
    assert first == second
    assert all(isinstance(b, KillBreach) for b in first)


# --- §5 acceptance: pre-committed (no-hindsight) dates -----------------------


def test_thesis_must_predate_acquisition() -> None:
    """A thesis dated after the lot is a hindsight violation — it raises."""
    acq = AS_OF - timedelta(days=400)
    lot = _lot(acq=acq, cost=Decimal("100"), mv=Decimal("70"))
    late = _thesis(
        effective=acq + timedelta(days=1),
        kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")),
    )
    with pytest.raises(ThesisError, match="pre-commitment"):
        evaluate_kill_criteria(lot, late, as_of=AS_OF)


def test_thesis_same_day_as_acquisition_is_pre_committed() -> None:
    """effective_date == acquisition_date is allowed (on-or-before rule)."""
    acq = AS_OF - timedelta(days=400)
    lot = _lot(acq=acq, cost=Decimal("100"), mv=Decimal("70"))
    same_day = _thesis(
        effective=acq,
        kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")),
    )
    breaches = evaluate_kill_criteria(lot, same_day, as_of=AS_OF)
    assert len(breaches) == 1


def test_mis_keyed_thesis_raises() -> None:
    lot = _lot(ticker="AAPL")
    other = _thesis(
        instrument="VTI",
        kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")),
    )
    with pytest.raises(ThesisError, match="does not key"):
        evaluate_kill_criteria(lot, other, as_of=AS_OF)


# --- the other three kill criteria ------------------------------------------


def test_liquidity_floor_breach() -> None:
    lot = _lot(liquidity_tier=4)
    thesis = _thesis(kill=KillCriteria(min_liquidity_tier=3))
    breaches = evaluate_kill_criteria(lot, thesis, as_of=AS_OF)
    assert [b.criterion for b in breaches] == [KillCriterion.LIQUIDITY_FLOOR]


def test_horizon_breach() -> None:
    acq = AS_OF - timedelta(days=365 * 3)
    lot = _lot(acq=acq)
    thesis = _thesis(
        effective=acq - timedelta(days=1),
        kill=KillCriteria(max_holding_years=Decimal("1")),
    )
    breaches = evaluate_kill_criteria(lot, thesis, as_of=AS_OF)
    assert [b.criterion for b in breaches] == [KillCriterion.HORIZON]


def test_residual_cap_needs_active_return() -> None:
    lot = _lot(cost=Decimal("100"), mv=Decimal("107"))
    thesis = _thesis(kill=KillCriteria(max_active_residual=Decimal("0.02")))
    # No active_return supplied → residual cap cannot be evaluated → no breach.
    assert evaluate_kill_criteria(lot, thesis, as_of=AS_OF) == []
    # Supplied (from attribution) and over cap → breach.
    breaches = evaluate_kill_criteria(
        lot, thesis, as_of=AS_OF, active_return=Decimal("0.05")
    )
    assert [b.criterion for b in breaches] == [KillCriterion.RESIDUAL_CAP]


# --- §5 acceptance: checkpoint 1 flips off the pa0 stub ----------------------


def test_checkpoint_1_not_documented_when_no_matching_thesis() -> None:
    report = _report([_lot(cost=Decimal("100"), mv=Decimal("107"))])
    store = ThesisStore.from_theses(
        [
            _thesis(
                instrument="OTHER",
                kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")),
            )
        ]
    )
    review = score_analyst_checkpoints(report, theses=store)
    assert review.checkpoints["checkpoint_1"] == _S.NOT_DOCUMENTED


def test_checkpoint_1_pass_with_thesis_no_breach() -> None:
    report = _report([_lot(cost=Decimal("100"), mv=Decimal("107"))])
    store = ThesisStore.from_theses(
        [_thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.90")))]
    )
    review = score_analyst_checkpoints(report, theses=store)
    assert review.checkpoints["checkpoint_1"] == _S.PASS


def test_checkpoint_1_breach_with_thesis_breach() -> None:
    report = _report([_lot(cost=Decimal("100"), mv=Decimal("70"))])
    store = ThesisStore.from_theses(
        [_thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")))]
    )
    review = score_analyst_checkpoints(report, theses=store)
    assert review.checkpoints["checkpoint_1"] == _S.BREACH


def test_checkpoint_1_accepts_plain_thesis_list() -> None:
    report = _report([_lot(cost=Decimal("100"), mv=Decimal("107"))])
    theses = [
        _thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.90")))
    ]
    review = score_analyst_checkpoints(report, theses=theses)
    assert review.checkpoints["checkpoint_1"] == _S.PASS


# --- §9 fixture flow: concentrated_stress trips a real breach ---------------


def test_concentrated_stress_flow_breaches_no_persist() -> None:
    bundle = emit_synthetic_household(
        cohort_id="concentrated_stress", seed=42, rung=4, validate=False
    )
    fixture = bundle.fixture
    as_of = synthetic_thesis_as_of(fixture)
    positions = lot_positions_from_fixture(fixture)
    store = ThesisStore.from_theses(emit_synthetic_theses(fixture))

    report = evaluate_attribution(
        positions,
        EXPECTED,
        household_id=fixture.household_id,
        as_of=as_of,
        config_version="2026.06",
        min_holding_years=Decimal("0.5"),
    )
    active = {
        (pa.account_id, pa.ticker): pa.active_return for pa in report.positions
    }
    all_breaches: list[KillBreach] = []
    for pos in positions:
        thesis = store.get(pos.account_id, pos.ticker or "")
        if thesis is None:
            continue
        all_breaches.extend(
            evaluate_kill_criteria(
                pos,
                thesis,
                as_of=as_of,
                active_return=active.get((pos.account_id, pos.ticker)),
            )
        )
    # The concentrated AAPL loss lot trips the tighter drawdown kill.
    assert all_breaches
    assert all(isinstance(b, KillBreach) for b in all_breaches)
    assert any(
        b.criterion == KillCriterion.DRAWDOWN_VS_COST for b in all_breaches
    )


# --- dashboard panel --------------------------------------------------------


def test_kill_criteria_panel_renders_breaches() -> None:
    data = load_kill_criteria_dashboard()
    assert data.error is None
    assert data.thesis_count > 0
    assert data.breaches
    html = render_analyst_section(data)
    assert "Kill-criteria watch" in html
    assert "Alerts only" in html
    assert data.breaches[0].instrument in html
