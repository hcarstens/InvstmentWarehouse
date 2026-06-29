"""ST6 property-based invariants for constrained MV QP (st5d).

Independent oracles (ST2): budget sum, box bounds, portfolio variance from
μ/Σ math, turnover L1 — never weights copied from ``solve_qp`` output.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.optimizer.models import OptimizerInfeasibleError
from warehouse.decision.optimizer.qp import project_capped_simplex, solve_qp
from warehouse.decision.optimizer.rebalance import run_mv_rebalance
from warehouse.research.risk.assumptions import build_assumptions
from warehouse.research.risk.models import AssetClass as RiskClass

_BUDGET_TOL = 1e-6
_SUM_TOL = Decimal("0.0001")
_QP_KW = {"tol": 1e-9, "max_iters": 5000}

QpProblem = tuple[
    list[float],
    list[list[float]],
    list[float],
    list[float],
    float,
]

# --- independent oracles -----------------------------------------------------


def _oracle_budget_sum(
    weights: list[float],
    *,
    total: float = 1.0,
    tol: float = _BUDGET_TOL,
) -> bool:
    return abs(sum(weights) - total) <= tol


def _oracle_box_feasible(
    weights: list[float],
    w_min: list[float],
    w_max: list[float],
    *,
    tol: float = 1e-9,
) -> bool:
    return all(
        w_min[i] - tol <= weights[i] <= w_max[i] + tol
        for i in range(len(weights))
    )


def _oracle_portfolio_variance(
    weights: list[float],
    sigma: list[list[float]],
) -> float:
    n = len(weights)
    return sum(
        weights[i] * sigma[i][j] * weights[j]
        for i in range(n)
        for j in range(n)
    )


def _oracle_turnover_l1(delta: dict[object, Decimal]) -> Decimal:
    return sum((abs(d) for d in delta.values()), Decimal("0"))


# --- hypothesis strategies ---------------------------------------------------


@st.composite
def feasible_box(draw: st.DrawFn) -> tuple[list[float], list[float]]:
    """Box ∩ simplex feasible: Σw_min ≤ 1 ≤ Σw_max, w_min[i] ≤ w_max[i]."""
    n = draw(st.integers(min_value=2, max_value=5))
    raw_mins = draw(
        st.lists(
            st.floats(
                min_value=0.0,
                max_value=0.35,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=n,
            max_size=n,
        )
    )
    sum_min = sum(raw_mins)
    if sum_min > 0.95:
        scale = 0.9 / sum_min
        w_min = [m * scale for m in raw_mins]
    else:
        w_min = list(raw_mins)
    w_max: list[float] = []
    for lo in w_min:
        hi = draw(
            st.floats(
                min_value=lo,
                max_value=1.0,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        w_max.append(hi)
    if sum(w_max) < 1.0:
        deficit = 1.0 - sum(w_max)
        per = deficit / n
        w_max = [min(hi + per, 1.0) for hi in w_max]
    assume(sum(w_min) <= 1.0 + 1e-9)
    assume(sum(w_max) >= 1.0 - 1e-9)
    return w_min, w_max


@st.composite
def psd_sigma(draw: st.DrawFn, n: int) -> list[list[float]]:
    """Diagonal PSD Σ — hunts near-singular vol edges (ST6)."""
    vols = draw(
        st.lists(
            st.floats(
                min_value=1e-8,
                max_value=0.5,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=n,
            max_size=n,
        )
    )
    return [[vols[i] * vols[j] for j in range(n)] for i in range(n)]


@st.composite
def qp_problem(draw: st.DrawFn) -> QpProblem:
    w_min, w_max = draw(feasible_box())
    n = len(w_min)
    mu = draw(
        st.lists(
            st.floats(
                min_value=-0.2,
                max_value=0.3,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=n,
            max_size=n,
        )
    )
    sigma = draw(psd_sigma(n))
    lam = draw(
        st.floats(
            min_value=1e-6,
            max_value=100.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    return mu, sigma, w_min, w_max, lam


# --- turnover fixtures (minimal) ---------------------------------------------


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


def _ips_with_budget(
    budget: Decimal,
) -> InvestmentPolicyStatement:
    return InvestmentPolicyStatement(
        ips_id="ips_test",
        household_id="hh_test",
        version=1,
        effective_date="2026-01-01",
        turnover_budget_pct=budget,
        allocation_targets=[
            AllocationTarget(
                asset_class="equity",  # type: ignore[arg-type]
                min_weight=Decimal("0"),
                max_weight=Decimal("1"),
                target_weight=Decimal("0.5"),
            ),
            AllocationTarget(
                asset_class="fixed_income",  # type: ignore[arg-type]
                min_weight=Decimal("0"),
                max_weight=Decimal("1"),
                target_weight=Decimal("0.5"),
            ),
        ],
    )


def _equity_favoring_assumptions():
    vol = {c: Decimal("0.20") for c in RiskClass}
    vol[RiskClass.EQUITY] = Decimal("0.10")
    vol[RiskClass.FIXED_INCOME] = Decimal("0.05")
    mu = {c: Decimal("0.01") for c in RiskClass}
    mu[RiskClass.EQUITY] = Decimal("0.12")
    mu[RiskClass.FIXED_INCOME] = Decimal("0.02")
    return build_assumptions(
        class_annual_vol=vol,
        class_expected_return=mu,
        class_correlations={},
        default_class_correlation=Decimal("0"),
    )


def _bond_heavy_positions() -> list[LotPositionView]:
    return [
        _lot("VTI", SecClass.EQUITY, Decimal("10")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("90")),
    ]


# --- solve_qp / projection properties ----------------------------------------


@given(problem=qp_problem())
def test_solve_qp_budget_sums_to_one(problem: QpProblem) -> None:
    mu, sigma, w_min, w_max, lam = problem
    w = solve_qp(mu, sigma, w_min, w_max, lam=lam, **_QP_KW)
    assert _oracle_budget_sum(w)


@given(problem=qp_problem())
def test_solve_qp_respects_box_bounds(problem: QpProblem) -> None:
    mu, sigma, w_min, w_max, lam = problem
    w = solve_qp(mu, sigma, w_min, w_max, lam=lam, **_QP_KW)
    assert _oracle_box_feasible(w, w_min, w_max)


@given(bounds=feasible_box())
def test_project_capped_simplex_budget(
    bounds: tuple[list[float], list[float]],
) -> None:
    w_min, w_max = bounds
    n = len(w_min)
    v = [1.0 / n] * n
    w = project_capped_simplex(v, w_min, w_max)
    assert _oracle_budget_sum(w)
    assert _oracle_box_feasible(w, w_min, w_max)


@given(
    bounds=feasible_box(),
    v=st.lists(
        st.floats(
            min_value=-1.0,
            max_value=2.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=2,
        max_size=5,
    ),
)
def test_project_capped_simplex_random_v(
    bounds: tuple[list[float], list[float]],
    v: list[float],
) -> None:
    w_min, w_max = bounds
    assume(len(v) == len(w_min))
    w = project_capped_simplex(v, w_min, w_max)
    assert _oracle_budget_sum(w)
    assert _oracle_box_feasible(w, w_min, w_max)


@given(
    lam_spread=st.floats(
        min_value=2.0,
        max_value=50.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    problem=qp_problem(),
)
def test_monotone_risk_aversion_parametric(
    lam_spread: float,
    problem: QpProblem,
) -> None:
    mu, sigma, w_min, w_max, lam_low = problem
    lam_high = lam_low * lam_spread
    w_low = solve_qp(mu, sigma, w_min, w_max, lam=lam_low, **_QP_KW)
    w_high = solve_qp(mu, sigma, w_min, w_max, lam=lam_high, **_QP_KW)
    var_low = _oracle_portfolio_variance(w_low, sigma)
    var_high = _oracle_portfolio_variance(w_high, sigma)
    assert var_high <= var_low + 1e-5


# --- infeasibility (errors bubble — no silent clip) --------------------------


def test_infeasible_sum_w_min_raises() -> None:
    with pytest.raises(OptimizerInfeasibleError, match="w_min"):
        solve_qp(
            mu=[0.0, 0.0],
            sigma=[[0.01, 0.0], [0.0, 0.01]],
            w_min=[0.6, 0.6],
            w_max=[1.0, 1.0],
            lam=1.0,
            **_QP_KW,
        )


def test_infeasible_sum_w_max_raises() -> None:
    with pytest.raises(OptimizerInfeasibleError, match="w_max"):
        solve_qp(
            mu=[0.0, 0.0],
            sigma=[[0.01, 0.0], [0.0, 0.01]],
            w_min=[0.0, 0.0],
            w_max=[0.3, 0.3],
            lam=1.0,
            **_QP_KW,
        )


@given(
    overshoot=st.floats(
        min_value=1e-6,
        max_value=0.2,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_infeasible_box_sum_w_min_property(overshoot: float) -> None:
    with pytest.raises(OptimizerInfeasibleError, match="w_min"):
        solve_qp(
            mu=[0.05, 0.05],
            sigma=[[0.04, 0.0], [0.0, 0.04]],
            w_min=[0.5 + overshoot / 2, 0.5 + overshoot / 2],
            w_max=[1.0, 1.0],
            lam=1.0,
            **_QP_KW,
        )


@given(
    undershoot=st.floats(
        min_value=1e-6,
        max_value=0.2,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_infeasible_box_sum_w_max_property(undershoot: float) -> None:
    with pytest.raises(OptimizerInfeasibleError, match="w_max"):
        solve_qp(
            mu=[0.05, 0.05],
            sigma=[[0.04, 0.0], [0.0, 0.04]],
            w_min=[0.0, 0.0],
            w_max=[0.5 - undershoot / 2, 0.5 - undershoot / 2],
            lam=1.0,
            **_QP_KW,
        )


# --- turnover budget (run_mv_rebalance) --------------------------------------


@given(
    budget=st.decimals(
        min_value=Decimal("0.05"),
        max_value=Decimal("0.30"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_turnover_within_budget_when_binding(budget: Decimal) -> None:
    proposal = run_mv_rebalance(
        _bond_heavy_positions(),
        _ips_with_budget(budget),
        assumptions=_equity_favoring_assumptions(),
        compute_stress=False,
    )
    assert _oracle_budget_sum(
        [float(w) for w in proposal.target_weights.values()],
        tol=float(_SUM_TOL),
    )
    if proposal.turnover_binding:
        assert proposal.turnover_l1 <= budget + _SUM_TOL
        assert proposal.turnover_budget == budget
    oracle_turnover = _oracle_turnover_l1(proposal.delta_w)
    assert proposal.turnover_l1 == oracle_turnover


def test_near_singular_sigma_still_feasible() -> None:
    w = solve_qp(
        mu=[0.10, 0.05],
        sigma=[[1e-10, 0.0], [0.0, 0.04]],
        w_min=[0.0, 0.0],
        w_max=[1.0, 1.0],
        lam=1.0,
        **_QP_KW,
    )
    assert _oracle_budget_sum(w)
    assert _oracle_box_feasible(w, [0.0, 0.0], [1.0, 1.0])


def test_lambda_near_zero_budget_and_box() -> None:
    w = solve_qp(
        mu=[0.20, 0.0],
        sigma=[[0.01, 0.0], [0.0, 0.01]],
        w_min=[0.0, 0.0],
        w_max=[0.3, 1.0],
        lam=1e-12,
        **_QP_KW,
    )
    assert _oracle_budget_sum(w)
    assert _oracle_box_feasible(w, [0.0, 0.0], [0.3, 1.0])
