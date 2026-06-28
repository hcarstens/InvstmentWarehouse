"""po0 run_mv_rebalance — universe, RC, advisory, turnover, drift, flags."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.optimizer.heuristics import run_tax_aware_optimizer
from warehouse.decision.optimizer.models import RebalanceProposal
from warehouse.decision.optimizer.rebalance import run_mv_rebalance


def _lot(
    ticker: str,
    sec: SecClass,
    mv: Decimal,
    *,
    gain: Decimal = Decimal("0"),
) -> LotPositionView:
    cost = mv - gain
    return LotPositionView(
        lot_id=f"lot_{ticker}",
        account_id="acct_test",
        account_name="Test",
        security_id=ticker,
        ticker=ticker,
        security_name=ticker,
        security_asset_class=sec,
        liquidity_tier=1,
        quantity=Decimal("1"),
        cost_basis_per_share=cost,
        total_cost_basis=cost,
        market_price=mv,
        market_value=mv,
        unrealized_gain=gain,
        acquisition_date=date(2019, 1, 1),
        is_restricted=False,
        wash_sale_substitute_group=None,
    )


def _ips(
    targets: list[tuple[str, str, str, str]],
) -> InvestmentPolicyStatement:
    return InvestmentPolicyStatement(
        ips_id="ips_test",
        household_id="hh_test",
        version=1,
        effective_date="2026-01-01",
        allocation_targets=[
            AllocationTarget(
                asset_class=ac,  # type: ignore[arg-type]
                min_weight=Decimal(lo),
                max_weight=Decimal(hi),
                target_weight=Decimal(tw),
            )
            for ac, lo, hi, tw in targets
        ],
    )


def test_universe_is_positions_union_targets() -> None:
    """Universe = sleeves in positions ∪ sleeves in IPS targets."""
    positions = [_lot("VTI", SecClass.EQUITY, Decimal("100"))]
    # IPS names fixed_income (no position) — must still appear in the universe.
    ips = _ips(
        [
            ("equity", "0", "1", "0.6"),
            ("fixed_income", "0", "1", "0.4"),
        ]
    )
    proposal = run_mv_rebalance(positions, ips)
    assert set(proposal.target_weights) == {
        IpsSleeve.EQUITY,
        IpsSleeve.FIXED_INCOME,
    }
    # fixed_income has no position → current weight 0.
    assert proposal.current_weights[IpsSleeve.FIXED_INCOME] == Decimal("0")


def test_risk_contributions_sum_to_one() -> None:
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("60")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("40")),
    ]
    ips = _ips(
        [
            ("equity", "0", "1", "0.6"),
            ("fixed_income", "0", "1", "0.4"),
        ]
    )
    proposal = run_mv_rebalance(positions, ips)
    total_rc = sum(proposal.risk_contributions.values(), Decimal("0"))
    assert abs(total_rc - Decimal("1")) < Decimal("0.01")


def test_rebalance_is_advisory_no_trade() -> None:
    """The QP leg returns weights only — it carries no trade objects."""
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("60")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("40")),
    ]
    ips = _ips(
        [
            ("equity", "0", "1", "0.6"),
            ("fixed_income", "0", "1", "0.4"),
        ]
    )
    proposal = run_mv_rebalance(positions, ips)
    assert isinstance(proposal, RebalanceProposal)
    assert not hasattr(proposal, "trades")


def test_rebalance_coexists_with_tlh_trades() -> None:
    """v0 TLH sells + po0 rebalance coexist; neither path is the other."""
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("60"), gain=Decimal("-20")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("40")),
    ]
    ips = _ips(
        [
            ("equity", "0", "1", "0.6"),
            ("fixed_income", "0", "1", "0.4"),
        ]
    )
    tlh = run_tax_aware_optimizer("hh_test", positions, ips)
    rebalance = run_mv_rebalance(positions, ips)
    result = tlh.model_copy(update={"rebalance": rebalance})
    assert len(result.trades) > 0  # TLH harvested the loss lot
    assert result.rebalance is not None
    # The rebalance path produced no trades of its own.
    assert result.trades == tlh.trades


def test_turnover_l1_equals_sum_abs_delta() -> None:
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("80")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("20")),
    ]
    ips = _ips(
        [
            ("equity", "0.3", "0.6", "0.5"),
            ("fixed_income", "0.4", "0.7", "0.5"),
        ]
    )
    proposal = run_mv_rebalance(positions, ips)
    expected = sum((abs(d) for d in proposal.delta_w.values()), Decimal("0"))
    assert proposal.turnover_l1 == expected


def test_policy_drift_reported() -> None:
    """policy_drift[s] = w_current[s] − IPS target_weight[s]."""
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("80")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("20")),
    ]
    ips = _ips(
        [
            ("equity", "0", "1", "0.6"),
            ("fixed_income", "0", "1", "0.4"),
        ]
    )
    proposal = run_mv_rebalance(positions, ips)
    # current equity = 0.8, target 0.6 → drift +0.2.
    assert proposal.policy_drift[IpsSleeve.EQUITY] == Decimal("0.8") - Decimal(
        "0.6"
    )


def test_illiquid_sleeve_flagged_when_in_universe() -> None:
    """ALTERNATIVES present → flagged, sleeve-level (even at Δw≈0)."""
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("70")),
        _lot("SYNPE", SecClass.ALTERNATIVE, Decimal("30")),
    ]
    ips = _ips(
        [
            ("equity", "0", "1", "0.7"),
            ("alternatives", "0", "1", "0.3"),
        ]
    )
    proposal = run_mv_rebalance(positions, ips)
    assert IpsSleeve.ALTERNATIVES in proposal.illiquid_advisory_sleeves


def test_unbounded_sleeve_flagged() -> None:
    """A sleeve in positions but absent from IPS targets → unbounded flag."""
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("60")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("40")),
    ]
    # IPS only constrains equity; fixed_income is free (no target).
    ips = _ips([("equity", "0", "1", "1.0")])
    proposal = run_mv_rebalance(positions, ips)
    assert IpsSleeve.FIXED_INCOME in proposal.unbounded_sleeves
    assert proposal.policy_drift[IpsSleeve.FIXED_INCOME] == Decimal("0")
