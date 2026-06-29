"""st5e — analyst boundary oracles (kill-criteria, NPA, attribution).

Independent oracles (ST2): window de-annualization and breach thresholds —
never copied from production helpers under test.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from warehouse.config import get_settings
from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.analyst import (
    AnalystCheckpointScore,
    AttributionError,
    KillCriteria,
    KillCriterion,
    NpaReason,
    PositionThesis,
    ThesisError,
    breaches_for_attribution,
    evaluate_attribution,
    evaluate_kill_criteria,
    flag_non_performing,
    position_active_score,
    risk_class_for,
    score_analyst_checkpoints,
)
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.research.risk.scenarios import assumptions_for
from warehouse.research.synthetic.models import (
    SyntheticAltCall,
    SyntheticAltHolding,
)

AS_OF = date(2026, 6, 28)
CONFIG_VERSION = "2026.06"
STALE_DAYS = 180
DRAWDOWN = Decimal("-0.10")
SUSTAINED = Decimal("1.0")
EXPECTED = assumptions_for("base").class_expected_return
_ONE = Decimal("1")
_DAYS_PER_YEAR = Decimal("365.25")
_S = AnalystCheckpointScore
_QUANTUM = Decimal("0.000001")


# --- independent oracles -----------------------------------------------------


def _oracle_expected_cumulative(
    class_expected: Decimal,
    holding_years: Decimal,
) -> Decimal:
    return (_ONE + class_expected) ** holding_years - _ONE


def _oracle_active_return(
    total_return: Decimal,
    expected_cumulative: Decimal,
) -> Decimal:
    return total_return - expected_cumulative


def _holding_years(acq: date, as_of: date = AS_OF) -> Decimal:
    days = max((as_of - acq).days, 0)
    return Decimal(days) / _DAYS_PER_YEAR


# --- shared fixtures ---------------------------------------------------------


def _lot(
    *,
    lot_id: str = "lot",
    ticker: str = "AAPL",
    asset_class: SecClass = SecClass.EQUITY,
    acq: date = AS_OF - timedelta(days=800),
    cost: Decimal = Decimal("100"),
    mv: Decimal | None = Decimal("100"),
    liquidity_tier: int = 1,
) -> LotPositionView:
    gain = (mv - cost) if mv is not None else None
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
        unrealized_gain=gain,
        acquisition_date=acq,
        is_restricted=False,
        wash_sale_substitute_group=None,
    )


def _thesis(*, kill: KillCriteria) -> PositionThesis:
    return PositionThesis(
        account_id="acct",
        instrument="AAPL",
        mechanism="test",
        effective_date=AS_OF - timedelta(days=900),
        kill_criteria=kill,
        config_version=CONFIG_VERSION,
    )


def _alt(
    *,
    last_mark: date = AS_OF - timedelta(days=30),
    unfunded: Decimal = Decimal("0"),
    calls: list[SyntheticAltCall] | None = None,
) -> SyntheticAltHolding:
    return SyntheticAltHolding(
        holding_id="pe-1",
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


def _flag(positions, alts, ips=None):
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


# --- attribution oracles (ST2) -----------------------------------------------


def test_attribution_oracle_matches_window_deannualization() -> None:
    acq = AS_OF - timedelta(days=400)
    cost = Decimal("100")
    mv = Decimal("130")
    lot = _lot(acq=acq, cost=cost, mv=mv)
    report = evaluate_attribution(
        [lot],
        EXPECTED,
        household_id="hh",
        as_of=AS_OF,
        config_version=CONFIG_VERSION,
        min_holding_years=Decimal("0.5"),
    )
    pa = report.positions[0]
    years = _holding_years(acq)
    class_exp = EXPECTED[risk_class_for(SecClass.EQUITY)]
    expected = _oracle_expected_cumulative(class_exp, years)
    active = _oracle_active_return(pa.total_return, expected)
    assert abs(pa.expected_cumulative - expected) <= _QUANTUM
    assert abs(pa.active_return - active) <= _QUANTUM
    recombined = pa.expected_cumulative + pa.active_return
    assert abs(recombined - pa.total_return) <= _QUANTUM


def test_attribution_missing_market_value_raises() -> None:
    lot = _lot(mv=None)
    with pytest.raises(AttributionError, match="no market value"):
        evaluate_attribution(
            [lot],
            EXPECTED,
            household_id="hh",
            as_of=AS_OF,
            config_version=CONFIG_VERSION,
            min_holding_years=Decimal("0.5"),
        )


def test_attribution_zero_cost_basis_raises() -> None:
    lot = _lot(cost=Decimal("0"), mv=Decimal("100"))
    with pytest.raises(AttributionError, match="non-positive cost basis"):
        evaluate_attribution(
            [lot],
            EXPECTED,
            household_id="hh",
            as_of=AS_OF,
            config_version=CONFIG_VERSION,
            min_holding_years=Decimal("0.5"),
        )


def test_checkpoint_2_warn_between_thresholds() -> None:
    settings = get_settings()
    warn = Decimal(str(settings.analyst_residual_warn))
    breach = Decimal(str(settings.analyst_residual_breach))
    eq_exp = EXPECTED[risk_class_for(SecClass.EQUITY)]
    target_active = (warn + breach) / 2
    total_return = target_active + eq_exp
    lot = _lot(
        acq=AS_OF - timedelta(days=365),
        cost=Decimal("100"),
        mv=Decimal("100") * (_ONE + total_return),
    )
    report = evaluate_attribution(
        [lot],
        EXPECTED,
        household_id="hh",
        as_of=AS_OF,
        config_version=CONFIG_VERSION,
        min_holding_years=Decimal("0.5"),
    )
    pa = report.positions[0]
    assert position_active_score(pa, warn, breach) == _S.WARN
    review = score_analyst_checkpoints(report)
    assert review.checkpoints["checkpoint_2"] == _S.WARN


def test_analyst_gaps_not_computed() -> None:
    """§6 acceptance alias — valuation/factor checkpoints stay honest."""
    report = evaluate_attribution(
        [_lot(cost=Decimal("100"), mv=Decimal("107"))],
        EXPECTED,
        household_id="hh",
        as_of=AS_OF,
        config_version=CONFIG_VERSION,
        min_holding_years=Decimal("0.5"),
    )
    review = score_analyst_checkpoints(report)
    assert review.checkpoints["checkpoint_3"] == _S.NOT_COMPUTED
    assert review.checkpoints["checkpoint_4"] == _S.NOT_COMPUTED
    assert review.checkpoints["checkpoint_6"] == _S.NOT_COMPUTED


# --- kill-criteria edges (ST6) -----------------------------------------------


def test_drawdown_kill_exactly_at_threshold_breaches() -> None:
    lot = _lot(cost=Decimal("100"), mv=Decimal("80"))  # −0.20
    thesis = _thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")))
    breaches = evaluate_kill_criteria(lot, thesis, as_of=AS_OF)
    assert len(breaches) == 1
    assert breaches[0].criterion == KillCriterion.DRAWDOWN_VS_COST


def test_drawdown_just_above_threshold_no_breach() -> None:
    lot = _lot(cost=Decimal("100"), mv=Decimal("81"))  # −0.19
    thesis = _thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")))
    assert evaluate_kill_criteria(lot, thesis, as_of=AS_OF) == []


def test_residual_cap_exactly_at_threshold_breaches() -> None:
    lot = _lot(cost=Decimal("100"), mv=Decimal("107"))
    thesis = _thesis(kill=KillCriteria(max_active_residual=Decimal("0.02")))
    breaches = evaluate_kill_criteria(
        lot, thesis, as_of=AS_OF, active_return=Decimal("0.02")
    )
    assert [b.criterion for b in breaches] == [KillCriterion.RESIDUAL_CAP]


def test_residual_cap_just_below_threshold_no_breach() -> None:
    lot = _lot(cost=Decimal("100"), mv=Decimal("107"))
    thesis = _thesis(kill=KillCriteria(max_active_residual=Decimal("0.02")))
    assert (
        evaluate_kill_criteria(
            lot, thesis, as_of=AS_OF, active_return=Decimal("0.019")
        )
        == []
    )


def test_horizon_exactly_at_max_no_breach() -> None:
    acq = AS_OF - timedelta(days=365)
    lot = _lot(acq=acq)
    thesis = _thesis(kill=KillCriteria(max_holding_years=Decimal("1")))
    assert evaluate_kill_criteria(lot, thesis, as_of=AS_OF) == []


def test_horizon_past_max_breaches() -> None:
    acq = AS_OF - timedelta(days=400)
    lot = _lot(acq=acq)
    thesis = _thesis(kill=KillCriteria(max_holding_years=Decimal("1")))
    breaches = evaluate_kill_criteria(lot, thesis, as_of=AS_OF)
    assert [b.criterion for b in breaches] == [KillCriterion.HORIZON]


def test_liquidity_tier_at_floor_no_breach() -> None:
    lot = _lot(liquidity_tier=3)
    thesis = _thesis(kill=KillCriteria(min_liquidity_tier=3))
    assert evaluate_kill_criteria(lot, thesis, as_of=AS_OF) == []


def test_liquidity_tier_worse_than_floor_breaches() -> None:
    lot = _lot(liquidity_tier=4)
    thesis = _thesis(kill=KillCriteria(min_liquidity_tier=3))
    breaches = evaluate_kill_criteria(lot, thesis, as_of=AS_OF)
    assert [b.criterion for b in breaches] == [KillCriterion.LIQUIDITY_FLOOR]


def test_kill_criteria_multiple_breaches() -> None:
    lot = _lot(
        cost=Decimal("100"),
        mv=Decimal("70"),
        liquidity_tier=5,
        acq=AS_OF - timedelta(days=800),
    )
    thesis = _thesis(
        kill=KillCriteria(
            max_drawdown_vs_cost=Decimal("-0.20"),
            min_liquidity_tier=3,
        )
    )
    criteria = {
        b.criterion for b in evaluate_kill_criteria(lot, thesis, as_of=AS_OF)
    }
    assert KillCriterion.DRAWDOWN_VS_COST in criteria
    assert KillCriterion.LIQUIDITY_FLOOR in criteria


def test_kill_criteria_empty_limits_no_breach() -> None:
    lot = _lot(cost=Decimal("100"), mv=Decimal("50"), liquidity_tier=5)
    thesis = _thesis(kill=KillCriteria())
    assert evaluate_kill_criteria(lot, thesis, as_of=AS_OF) == []


def test_kill_criteria_missing_market_value_raises() -> None:
    lot = _lot(mv=None)
    thesis = _thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")))
    with pytest.raises(ThesisError, match="no market value"):
        evaluate_kill_criteria(lot, thesis, as_of=AS_OF)


def test_kill_criteria_zero_cost_raises() -> None:
    lot = _lot(cost=Decimal("0"), mv=Decimal("100"))
    thesis = _thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")))
    with pytest.raises(ThesisError, match="non-positive cost basis"):
        evaluate_kill_criteria(lot, thesis, as_of=AS_OF)


def test_breaches_for_attribution_matches_position_eval() -> None:
    lot = _lot(cost=Decimal("100"), mv=Decimal("75"))
    thesis = _thesis(kill=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")))
    report = evaluate_attribution(
        [lot],
        EXPECTED,
        household_id="hh",
        as_of=AS_OF,
        config_version=CONFIG_VERSION,
        min_holding_years=Decimal("0.5"),
    )
    pa = report.positions[0]
    pos_breaches = evaluate_kill_criteria(lot, thesis, as_of=AS_OF)
    attr_breaches = breaches_for_attribution(pa, thesis)
    assert [b.criterion for b in pos_breaches] == [
        b.criterion for b in attr_breaches
    ]


# --- NPA boundaries (ST6) --------------------------------------------------


def test_npa_drawdown_exactly_at_threshold_flags() -> None:
    days = int(365.25 * float(SUSTAINED)) + 1
    lot = _lot(
        cost=Decimal("100"),
        mv=Decimal("90"),
        acq=AS_OF - timedelta(days=days),
    )
    flags = _flag([lot], [])
    assert [f.reason for f in flags] == [NpaReason.SUSTAINED_DRAWDOWN]


def test_npa_drawdown_just_above_threshold_no_flag() -> None:
    lot = _lot(
        cost=Decimal("100"),
        mv=Decimal("91"),
        acq=AS_OF - timedelta(days=int(365.25 * float(SUSTAINED))),
    )
    assert _flag([lot], []) == []


def test_npa_sustained_window_exactly_at_boundary_flags() -> None:
    days = int(365.25 * float(SUSTAINED)) + 1
    lot = _lot(
        cost=Decimal("100"),
        mv=Decimal("80"),
        acq=AS_OF - timedelta(days=days),
    )
    flags = _flag([lot], [])
    assert [f.reason for f in flags] == [NpaReason.SUSTAINED_DRAWDOWN]


def test_npa_sustained_window_just_under_no_flag() -> None:
    days = int(365.25 * float(SUSTAINED)) - 5
    lot = _lot(
        cost=Decimal("100"),
        mv=Decimal("80"),
        acq=AS_OF - timedelta(days=days),
    )
    assert _flag([lot], []) == []


def test_npa_stale_mark_at_boundary_not_flagged() -> None:
    alt = _alt(last_mark=AS_OF - timedelta(days=STALE_DAYS))
    assert _flag([], [alt]) == []


def test_npa_stale_mark_one_day_past_flags() -> None:
    alt = _alt(last_mark=AS_OF - timedelta(days=STALE_DAYS + 1))
    flags = _flag([], [alt])
    assert [f.reason for f in flags] == [NpaReason.STALE_ALT_MARK]


def test_npa_ips_liquidity_exactly_at_floor_no_flag() -> None:
    liquid = _lot(lot_id="liq", liquidity_tier=1, mv=Decimal("500"))
    illiquid = _lot(lot_id="ill", liquidity_tier=5, mv=Decimal("500"))
    ips = InvestmentPolicyStatement(
        ips_id="ips",
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
        liquidity_tier_min_pct=Decimal("0.50"),
    )
    assert _flag([liquid, illiquid], [], ips) == []


def test_npa_ips_liquidity_just_below_floor_flags() -> None:
    liquid = _lot(lot_id="liq", liquidity_tier=1, mv=Decimal("499"))
    illiquid = _lot(lot_id="ill", liquidity_tier=5, mv=Decimal("501"))
    ips = InvestmentPolicyStatement(
        ips_id="ips",
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
        liquidity_tier_min_pct=Decimal("0.50"),
    )
    flags = _flag([liquid, illiquid], [], ips)
    assert [f.reason for f in flags] == [NpaReason.IPS_LIQUIDITY_BREACH]


def test_npa_future_call_not_missed() -> None:
    call = SyntheticAltCall(
        event_id="c1",
        holding_id="pe-1",
        event_date=AS_OF + timedelta(days=1),
        amount=Decimal("100"),
    )
    alt = _alt(unfunded=Decimal("50"), calls=[call])
    assert _flag([], [alt]) == []
