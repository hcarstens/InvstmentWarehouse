"""po1 turnover-budget constraint — ROUTE B convex step (§B.3).

The hard cap ``‖Δw‖₁ ≤ τ`` reads ``ips.turnover_budget_pct``; when unset po1
is a no-op (byte-identical po0). ROUTE B takes the budget-scaled convex step
``w_budget = w_current + (τ/‖Δw‖₁)·(w* − w_current)`` — exact on the budget,
box- and simplex-feasible, advisory only (stages no trade).
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

_SUM_TOL = Decimal("0.0001")


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
    *,
    turnover_budget: str | None = None,
) -> InvestmentPolicyStatement:
    return InvestmentPolicyStatement(
        ips_id="ips_test",
        household_id="hh_test",
        version=1,
        effective_date="2026-01-01",
        turnover_budget_pct=(
            Decimal(turnover_budget) if turnover_budget is not None else None
        ),
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


def _equity_favoring_assumptions():
    """Equity dominates (high μ, low vol) so w* pulls hard off a bond-heavy
    book → a large unconstrained ‖Δw‖₁ the budget can bite."""
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


def _symmetric_assumptions():
    vol = {c: Decimal("0.10") for c in RiskClass}
    mu = {c: Decimal("0.05") for c in RiskClass}
    return build_assumptions(
        class_annual_vol=vol,
        class_expected_return=mu,
        class_correlations={},
        default_class_correlation=Decimal("0"),
    )


def _bond_heavy_positions() -> list[LotPositionView]:
    # Current ≈ 90% fixed income; the equity-favoring optimum wants the
    # opposite → unconstrained ‖Δw‖₁ is large.
    return [
        _lot("VTI", SecClass.EQUITY, Decimal("10")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("90")),
    ]


def test_turnover_budget_binds() -> None:
    """Slack box, ‖Δw*‖₁ > τ → result ‖Δw‖₁ ≤ τ, Σw=1, box-feasible, bound."""
    positions = _bond_heavy_positions()
    ips = _ips(
        [("equity", "0", "1", "0.5"), ("fixed_income", "0", "1", "0.5")],
        turnover_budget="0.10",
    )
    proposal = run_mv_rebalance(
        positions, ips, assumptions=_equity_favoring_assumptions()
    )
    assert proposal.turnover_binding is True
    assert proposal.unconstrained_turnover_l1 > Decimal("0.10")
    assert proposal.turnover_l1 <= Decimal("0.10") + _SUM_TOL
    # Σw = 1 and every weight inside its [min, max] box.
    total = sum(proposal.target_weights.values(), Decimal("0"))
    assert abs(total - Decimal("1")) <= _SUM_TOL
    for w in proposal.target_weights.values():
        assert Decimal("0") <= w <= Decimal("1")


def test_budget_step_is_convex_and_exact() -> None:
    """ROUTE B: on the binding case ‖Δw‖₁ == τ (within quantization)."""
    positions = _bond_heavy_positions()
    ips = _ips(
        [("equity", "0", "1", "0.5"), ("fixed_income", "0", "1", "0.5")],
        turnover_budget="0.12",
    )
    proposal = run_mv_rebalance(
        positions, ips, assumptions=_equity_favoring_assumptions()
    )
    assert proposal.turnover_binding is True
    assert abs(proposal.turnover_l1 - Decimal("0.12")) <= _SUM_TOL
    # The step moves TOWARD the unconstrained optimum (same sign per sleeve).
    unconstrained = run_mv_rebalance(
        positions,
        _ips([("equity", "0", "1", "0.5"), ("fixed_income", "0", "1", "0.5")]),
        assumptions=_equity_favoring_assumptions(),
    )
    for sleeve, d in proposal.delta_w.items():
        if unconstrained.delta_w[sleeve] != 0:
            assert (d >= 0) == (unconstrained.delta_w[sleeve] >= 0)


def test_turnover_budget_none_is_noop() -> None:
    """τ None → w* and turnover identical to po0 (regression)."""
    positions = _bond_heavy_positions()
    assumptions = _equity_favoring_assumptions()
    targets = [
        ("equity", "0", "1", "0.5"),
        ("fixed_income", "0", "1", "0.5"),
    ]
    no_budget = run_mv_rebalance(
        positions, _ips(targets), assumptions=assumptions
    )
    assert no_budget.turnover_budget is None
    assert no_budget.turnover_binding is False
    # Pre-cap and post-cap turnover coincide when there is no budget.
    assert no_budget.unconstrained_turnover_l1 == no_budget.turnover_l1


def test_turnover_budget_slack_unbinding() -> None:
    """τ larger than ‖Δw*‖₁ → w* unchanged, turnover_binding False."""
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("100")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("100")),
        _lot("CASH", SecClass.CASH, Decimal("100")),
    ]
    targets = [
        ("equity", "0", "1", "0.3333"),
        ("fixed_income", "0", "1", "0.3333"),
        ("cash", "0", "1", "0.3334"),
    ]
    assumptions = _symmetric_assumptions()
    unconstrained = run_mv_rebalance(
        positions, _ips(targets), assumptions=assumptions
    )
    proposal = run_mv_rebalance(
        positions,
        _ips(targets, turnover_budget="0.9"),
        assumptions=assumptions,
    )
    assert proposal.turnover_binding is False
    assert proposal.unconstrained_turnover_l1 <= Decimal("0.9")
    # w* is untouched by a non-binding budget.
    assert proposal.target_weights == unconstrained.target_weights


def test_turnover_advisory_no_trade() -> None:
    """po1 stages no trade; v0 TLH + budgeted rebalance coexist."""
    positions = [
        _lot("VTI", SecClass.EQUITY, Decimal("10"), gain=Decimal("-5")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("90")),
    ]
    ips = _ips(
        [("equity", "0", "1", "0.5"), ("fixed_income", "0", "1", "0.5")],
        turnover_budget="0.10",
    )
    tlh = run_tax_aware_optimizer("hh_test", positions, ips)
    rebalance = run_mv_rebalance(
        positions, ips, assumptions=_equity_favoring_assumptions()
    )
    result = tlh.model_copy(update={"rebalance": rebalance})
    assert result.rebalance is not None
    assert result.rebalance.turnover_binding is True
    # The rebalance path added no trades of its own.
    assert result.trades == tlh.trades
    assert not hasattr(rebalance, "trades")


def test_turnover_no_new_ops() -> None:
    """po1 stays behind optimizer.propose — no new atomic op (S1)."""
    import warehouse.messaging.handlers  # noqa: F401  (populates REGISTRY)
    from warehouse.messaging import REGISTRY as catalog

    pm_ops = {op for op in catalog if op.startswith("pm.")}
    assert pm_ops == {"pm.advise"}
    # po1 adds no optimizer op — the shipped surface is unchanged.
    opt_ops = {op for op in catalog if op.startswith("optimizer.")}
    assert opt_ops == {"optimizer.propose", "optimizer.persist"}
