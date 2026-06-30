"""po0 constrained-MV QP solver correctness (§7)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from warehouse.config import get_settings
from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.optimizer.models import OptimizerInfeasibleError
from warehouse.decision.optimizer.qp import solve_qp
from warehouse.decision.optimizer.rebalance import run_mv_rebalance
from warehouse.research.risk.assumptions import build_assumptions
from warehouse.research.risk.models import AssetClass as RiskClass


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
        acquisition_date=date(2020, 1, 1),
        is_restricted=False,
        wash_sale_substitute_group=None,
    )


def _symmetric_assumptions():
    """Equal μ/vol, zero correlation → uniform 1/n is the interior optimum."""
    vol = {c: Decimal("0.10") for c in RiskClass}
    mu = {c: Decimal("0.05") for c in RiskClass}
    return build_assumptions(
        class_annual_vol=vol,
        class_expected_return=mu,
        class_correlations={},
        default_class_correlation=Decimal("0"),
    )


def _wide_ips(sleeves: list[str]) -> InvestmentPolicyStatement:
    targets = [
        AllocationTarget(
            asset_class=s,  # type: ignore[arg-type]
            min_weight=Decimal("0"),
            max_weight=Decimal("1"),
            target_weight=Decimal(str(round(1 / len(sleeves), 4))),
        )
        for s in sleeves
    ]
    return InvestmentPolicyStatement(
        ips_id="ips_test",
        household_id="hh_test",
        version=1,
        effective_date="2026-01-01",
        allocation_targets=targets,
    )


def test_zero_delta_probe_pass_falsifier() -> None:
    """Current == constrained optimum → ‖Δw‖∞ ≈ 0, no binding bounds."""
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("100")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("100")),
        _lot("CASH", SecClass.CASH, Decimal("100")),
    ]
    ips = _wide_ips(["equity", "fixed_income", "cash"])
    proposal = run_mv_rebalance(
        positions, ips, assumptions=_symmetric_assumptions()
    )
    max_delta = max(abs(d) for d in proposal.delta_w.values())
    assert max_delta < Decimal("0.001")
    assert proposal.binding_bounds == []


def test_binding_sleeve_max_clip() -> None:
    """Optimum wants more of the high-μ asset → clips to its sleeve cap."""
    w = solve_qp(
        mu=[0.20, 0.0],
        sigma=[[0.01, 0.0], [0.0, 0.01]],
        w_min=[0.0, 0.0],
        w_max=[0.3, 1.0],
        lam=1.0,
        tol=1e-9,
        max_iters=5000,
    )
    assert abs(w[0] - 0.3) < 1e-4
    assert abs(w[1] - 0.7) < 1e-4


def test_lambda_monotonic_lowers_variance() -> None:
    """Higher λ → lower wᵀΣw at the optimum (more risk-averse)."""
    sigma = [[0.04, 0.0], [0.0, 0.01]]

    def variance(lam: float) -> float:
        w = solve_qp(
            mu=[0.10, 0.0],
            sigma=sigma,
            w_min=[0.0, 0.0],
            w_max=[1.0, 1.0],
            lam=lam,
            tol=1e-10,
            max_iters=20000,
        )
        return sum(
            w[i] * sigma[i][j] * w[j] for i in range(2) for j in range(2)
        )

    assert variance(50.0) < variance(1.0)


def test_infeasible_bounds_raise() -> None:
    with pytest.raises(OptimizerInfeasibleError, match="w_min"):
        solve_qp(
            mu=[0.0, 0.0],
            sigma=[[0.0, 0.0], [0.0, 0.0]],
            w_min=[0.6, 0.6],
            w_max=[1.0, 1.0],
            lam=1.0,
            tol=1e-9,
            max_iters=100,
        )
    with pytest.raises(OptimizerInfeasibleError, match="w_max"):
        solve_qp(
            mu=[0.0, 0.0],
            sigma=[[0.0, 0.0], [0.0, 0.0]],
            w_min=[0.0, 0.0],
            w_max=[0.3, 0.3],
            lam=1.0,
            tol=1e-9,
            max_iters=100,
        )


def test_target_weights_sum_to_one() -> None:
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("60")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("40")),
    ]
    ips = _wide_ips(["equity", "fixed_income"])
    proposal = run_mv_rebalance(positions, ips)
    total = sum(proposal.target_weights.values(), Decimal("0"))
    assert abs(total - Decimal("1")) <= Decimal("0.0001")


def test_all_constraints_binding_pinned_ips_falsifier() -> None:
    """qa5/H7 — pinned min=max on every sleeve; binding_bounds lists all."""
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("30")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("70")),
    ]
    ips = InvestmentPolicyStatement(
        ips_id="ips_test",
        household_id="hh_test",
        version=1,
        effective_date="2026-01-01",
        allocation_targets=[
            AllocationTarget(
                asset_class="equity",  # type: ignore[arg-type]
                min_weight=Decimal("0.3"),
                max_weight=Decimal("0.3"),
                target_weight=Decimal("0.3"),
            ),
            AllocationTarget(
                asset_class="fixed_income",  # type: ignore[arg-type]
                min_weight=Decimal("0.7"),
                max_weight=Decimal("0.7"),
                target_weight=Decimal("0.7"),
            ),
        ],
    )
    proposal = run_mv_rebalance(
        positions, ips, assumptions=_symmetric_assumptions()
    )
    assert proposal.target_weights[IpsSleeve.EQUITY] == Decimal("0.3")
    assert proposal.target_weights[IpsSleeve.FIXED_INCOME] == Decimal("0.7")
    assert set(proposal.binding_bounds) == {
        "ips_max:equity",
        "ips_max:fixed_income",
    }
    total = sum(proposal.target_weights.values(), Decimal("0"))
    assert abs(total - Decimal("1")) <= Decimal("0.0001")


def test_sigma_built_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """portfolio_covariance is called ONCE (at w*), never inside the loop."""
    import warehouse.decision.optimizer.rebalance as rebalance_mod

    calls = {"n": 0}
    real = rebalance_mod.portfolio_covariance

    def _counting(states, assumptions):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return real(states, assumptions)

    monkeypatch.setattr(rebalance_mod, "portfolio_covariance", _counting)
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("60")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("40")),
    ]
    ips = _wide_ips(["equity", "fixed_income"])
    # compute_stress=False isolates the base solve — the po2 overlay adds a
    # SECOND solve (one more portfolio_covariance call), so the "once per
    # solve, never inside the loop" invariant is checked on a single solve.
    run_mv_rebalance(
        positions, ips, settings=get_settings(), compute_stress=False
    )
    assert calls["n"] == 1
