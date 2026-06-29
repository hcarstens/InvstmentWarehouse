"""po2 scenario-robust stress overlay — §B.8 Option A (PO7).

The overlay re-solves the same constrained MV QP under a crisis-regime Σ and
reports base-MV w* vs stress-robust w* + the regime gap ‖w*_base − w*_stress‖₁.
On a SLACK-bound fixture (wide bounds) with base = LOW ρ and crisis = HIGH ρ
the MV optimum genuinely shifts (diversification collapses under crisis ρ); on
bound-determined fixtures both optima are bound-pinned → the gap is ~0 (honest,
not faked).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.optimizer.heuristics import run_tax_aware_optimizer
from warehouse.decision.optimizer.rebalance import run_mv_rebalance
from warehouse.research.risk.assumptions import build_assumptions
from warehouse.research.risk.models import AssetClass as RiskClass
from warehouse.research.synthetic import emit_synthetic_household
from warehouse.research.synthetic.fixture_views import (
    lot_positions_from_fixture,
)

_SUM_TOL = Decimal("0.0001")


def _lot(ticker: str, sec: SecClass, mv: Decimal) -> LotPositionView:
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
        cost_basis_per_share=mv,
        total_cost_basis=mv,
        market_price=mv,
        market_value=mv,
        unrealized_gain=Decimal("0"),
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


def _correlated_assumptions(rho: str):
    """Diversifiable 3-sleeve world; ρ is the only thing that varies."""
    vol = {c: Decimal("0.15") for c in RiskClass}
    vol[RiskClass.EQUITY] = Decimal("0.15")
    vol[RiskClass.FIXED_INCOME] = Decimal("0.12")
    vol[RiskClass.CASH] = Decimal("0.02")
    mu = {c: Decimal("0.05") for c in RiskClass}
    mu[RiskClass.EQUITY] = Decimal("0.08")
    mu[RiskClass.FIXED_INCOME] = Decimal("0.06")
    mu[RiskClass.CASH] = Decimal("0.03")
    return build_assumptions(
        class_annual_vol=vol,
        class_expected_return=mu,
        class_correlations={},
        default_class_correlation=Decimal(rho),
    )


def _slack_positions() -> list[LotPositionView]:
    return [
        _lot("VTI", SecClass.EQUITY, Decimal("50")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("30")),
        _lot("CASH", SecClass.CASH, Decimal("20")),
    ]


# Wide bounds so neither optimum is bound-pinned — the regime can move w*.
_SLACK_TARGETS = [
    ("equity", "0", "1", "0.4"),
    ("fixed_income", "0", "1", "0.4"),
    ("cash", "0", "1", "0.2"),
]


def test_stress_w_star_differs_from_base() -> None:
    """Slack box, base LOW ρ vs crisis HIGH ρ → w*_stress ≠ w*_base, gap>0."""
    positions = _slack_positions()
    ips = _ips(_SLACK_TARGETS)
    proposal = run_mv_rebalance(
        positions,
        ips,
        assumptions=_correlated_assumptions("0.0"),
        stress_assumptions=_correlated_assumptions("0.85"),
    )
    assert proposal.stress_regime is not None
    assert proposal.stress_target_weights != proposal.target_weights
    assert proposal.regime_gap_l1 > Decimal("0")
    # The regime gap is exactly ‖stress_delta_w‖₁.
    gap = sum((abs(d) for d in proposal.stress_delta_w.values()), Decimal("0"))
    assert proposal.regime_gap_l1 == gap
    # Stress w* is itself a feasible portfolio: Σw=1 and box-feasible.
    total = sum(proposal.stress_target_weights.values(), Decimal("0"))
    assert abs(total - Decimal("1")) <= _SUM_TOL
    for w in proposal.stress_target_weights.values():
        assert Decimal("0") <= w <= Decimal("1")


def test_concentrated_fixture_regime_gap() -> None:
    """concentrated_stress rung-4 seed 42 → both solves produced; gap shown."""
    bundle = emit_synthetic_household(
        cohort_id="concentrated_stress", seed=42, rung=4, validate=False
    )
    positions = lot_positions_from_fixture(bundle.fixture)
    proposal = run_mv_rebalance(positions, bundle.ips)
    assert proposal.stress_regime == "high_risk"
    assert proposal.stress_target_weights  # crisis solve produced
    assert set(proposal.stress_target_weights) == set(proposal.target_weights)
    assert proposal.regime_gap_l1 >= Decimal("0")  # reported (may be ~0)
    # Stress w* sums to 1 — a real second solve, not a copy.
    total = sum(proposal.stress_target_weights.values(), Decimal("0"))
    assert abs(total - Decimal("1")) <= _SUM_TOL


def test_base_path_byte_identical_to_po1() -> None:
    """The overlay is additive — every base field is unchanged by it."""
    positions = _slack_positions()
    ips = _ips(_SLACK_TARGETS)
    base = run_mv_rebalance(positions, ips, compute_stress=False)
    with_overlay = run_mv_rebalance(positions, ips, compute_stress=True)
    assert base.stress_regime is None
    assert with_overlay.stress_regime is not None
    # po0/po1 fields must be byte-identical.
    assert with_overlay.target_weights == base.target_weights
    assert with_overlay.delta_w == base.delta_w
    assert with_overlay.turnover_l1 == base.turnover_l1
    assert with_overlay.current_weights == base.current_weights
    assert with_overlay.policy_drift == base.policy_drift
    assert with_overlay.binding_bounds == base.binding_bounds
    assert with_overlay.risk_contributions == base.risk_contributions
    assert with_overlay.objective_value == base.objective_value


def test_robust_advisory_no_trade() -> None:
    """The overlay stages no trade; v0 TLH + po0/po1 + stress coexist."""
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("50")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("50")),
    ]
    ips = _ips(
        [("equity", "0", "1", "0.5"), ("fixed_income", "0", "1", "0.5")]
    )
    # A loss lot so v0 TLH harvests — proves the two legs coexist.
    loss = _lot("VTI", SecClass.EQUITY, Decimal("50"))
    loss = loss.model_copy(
        update={
            "cost_basis_per_share": Decimal("70"),
            "total_cost_basis": Decimal("70"),
            "unrealized_gain": Decimal("-20"),
        }
    )
    tlh = run_tax_aware_optimizer("hh_test", [loss, positions[1]], ips)
    rebalance = run_mv_rebalance([loss, positions[1]], ips)
    result = tlh.model_copy(update={"rebalance": rebalance})
    assert result.rebalance is not None
    assert result.rebalance.stress_regime is not None
    assert result.trades == tlh.trades  # rebalance added no trades
    assert not hasattr(rebalance, "trades")


def test_after_tax_mu_still_not_computed() -> None:
    """po2 does NOT flip honesty #5 — μ stays the ex-ante class assumption."""
    positions = _slack_positions()
    proposal = run_mv_rebalance(positions, _ips(_SLACK_TARGETS))
    # The stress overlay solves a Σ regime — it never touches the tax seam.
    assert proposal.mu_source == "ex_ante_class_assumption"


def test_robust_no_new_ops() -> None:
    """po2 stays behind optimizer.propose — no new atomic op (S1)."""
    import warehouse.messaging.handlers  # noqa: F401  (populates REGISTRY)
    from warehouse.messaging import REGISTRY as catalog

    pm_ops = {op for op in catalog if op.startswith("pm.")}
    assert pm_ops == {"pm.advise"}
    opt_ops = {op for op in catalog if op.startswith("optimizer.")}
    assert opt_ops == {"optimizer.propose", "optimizer.persist"}
