"""Constrained mean-variance rebalance (po0) — advisory w*/Δw/RC.

Assembles the sleeve universe (positions ∪ IPS targets), builds μ and Σ
**once** from the version-pinned risk priors (§A.2 — ``portfolio_covariance``
returns variance scalars, *not* the Σ matrix), solves the constrained MV QP
(``qp.solve_qp``), and reports the target vector, rebalance Δw, binding IPS
bounds, per-sleeve risk contributions, turnover, and policy drift (§B.2).

Pure and advisory: it stages **no trade** and persists nothing — the v0 TLH
``trades`` leg is unchanged and coexists on the same op (§B.1). μ is an
**ex-ante class assumption**, never a forecast (PO6).
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from warehouse.config import Settings, get_settings
from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.ips import InvestmentPolicyStatement
from warehouse.decision.ips.rollup import ips_sleeve_for_position
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.optimizer.models import (
    OptimizerInfeasibleError,
    OptimizerMappingError,
    RebalanceProposal,
)
from warehouse.decision.optimizer.qp import (
    project_capped_simplex,
    solve_qp,
)
from warehouse.decision.tax.estimator import TaxEstimator, ZeroTaxEstimator
from warehouse.research.risk.assumptions import RiskAssumptions
from warehouse.research.risk.covariance import (
    SleeveRiskState,
    portfolio_covariance,
)
from warehouse.research.risk.models import AllocationSlot
from warehouse.research.risk.models import AssetClass as RiskClass
from warehouse.research.risk.scenarios import assumptions_for

# Explicit, total sleeve→risk map. Does NOT rely on coincidental StrEnum
# cross-equality (§A.1): a naive ``class_expected_return[sleeve]`` join
# silently succeeds today and mis-prices μ/Σ the instant either enum drifts.
_SLEEVE_TO_RISK: dict[IpsSleeve, RiskClass] = {
    IpsSleeve.EQUITY: RiskClass.EQUITY,
    IpsSleeve.FIXED_INCOME: RiskClass.FIXED_INCOME,
    IpsSleeve.COMMODITIES: RiskClass.COMMODITIES,
    IpsSleeve.FX: RiskClass.FX,
    IpsSleeve.ALTERNATIVES: RiskClass.ALTERNATIVES,
    IpsSleeve.CASH: RiskClass.CASH,
}

# Sum-budget re-assertion tolerance after Decimal quantization (§A.2).
_SUM_TOLERANCE = Decimal("0.0001")
# Quantum for target/Δw weights — fine enough that Σw=1 holds to 1e-4.
_QUANTUM = Decimal("0.000001")
# Bound is "binding" when w* sits within this of a floor/cap.
_BIND_TOLERANCE = Decimal("0.0005")


def risk_class_for(sleeve: IpsSleeve) -> RiskClass:
    """Map an IPS sleeve to its risk-class analog, raising on drift (§A.1)."""
    try:
        return _SLEEVE_TO_RISK[sleeve]
    except KeyError as err:  # bubble to surface, never default
        raise OptimizerMappingError(
            f"no risk-class mapping for sleeve {sleeve!r}; cannot assign "
            "an expected return / covariance row"
        ) from err


def _current_weights(
    positions: list[LotPositionView],
) -> dict[IpsSleeve, Decimal]:
    total_mv = sum((p.market_value or Decimal("0")) for p in positions)
    if total_mv <= 0:
        raise ValueError("cannot rebalance — portfolio has no market value")
    weights: dict[IpsSleeve, Decimal] = {}
    for pos in positions:
        if pos.market_value is None:
            continue
        sleeve = ips_sleeve_for_position(pos)
        weights[sleeve] = (
            weights.get(sleeve, Decimal("0")) + pos.market_value / total_mv
        )
    return weights


def run_mv_rebalance(
    positions: list[LotPositionView],
    ips: InvestmentPolicyStatement,
    *,
    assumptions: RiskAssumptions | None = None,
    settings: Settings | None = None,
    tax_estimator: TaxEstimator | None = None,
    compute_stress: bool = True,
    stress_assumptions: RiskAssumptions | None = None,
) -> RebalanceProposal:
    """Constrained MV QP over sleeve weights → advisory ``RebalanceProposal``.

    Walk-forward safe: Σ/μ are the as-of base-regime priors; no realized-return
    lookahead (CLAUDE.md). Raises ``OptimizerMappingError`` on an unmapped
    sleeve and ``OptimizerInfeasibleError`` on an empty box∩simplex.

    ``tax_estimator`` is the po1-tax seam (§14 Addendum C): the default
    ``ZeroTaxEstimator`` is an identity overlay (after-tax μ ≡ pre-tax μ), so
    w* is byte-identical to the pre-overlay path and honesty matrix #5 stays
    ``not_computed`` — never faked. A non-zero estimator subtracts a per-sleeve
    drag from the ex-ante μ **before** the solve (overlay inside the IPS box,
    not a substitute).

    ``compute_stress`` enables the po2 scenario-robust overlay (§B.8 Option A):
    a SECOND solve under a crisis-regime Σ, reported alongside the base w* with
    the regime gap ``‖w*_base − w*_stress‖₁`` (PO7). It is additive — every
    base-path field is byte-identical whether or not it runs. ``False`` breaks
    the recursion when the overlay re-enters this function with the crisis
    priors. ``stress_assumptions`` overrides the crisis priors (tests inject a
    controlled high-ρ Σ); otherwise the version-pinned
    ``settings.optimizer_stress_regime`` (``high_risk``) is used.
    """
    cfg = settings or get_settings()
    priors = assumptions or assumptions_for("base")
    estimator = tax_estimator or ZeroTaxEstimator()

    current = _current_weights(positions)
    target_by_class = {t.asset_class: t for t in ips.allocation_targets}

    # Universe = sleeves in positions ∪ sleeves in IPS targets, in canonical
    # enum order for deterministic, audit-stable output.
    present = set(current) | set(target_by_class)
    universe = [s for s in IpsSleeve if s in present]

    risk_classes = [risk_class_for(s) for s in universe]

    # Build μ and Σ ONCE (float64) — the exact cov[i][j] formula in
    # covariance.py; portfolio_covariance is NOT called in the solve loop.
    vols = [float(priors.class_annual_vol[rc]) for rc in risk_classes]
    mu = [float(priors.class_expected_return[rc]) for rc in risk_classes]
    n = len(universe)

    # po1-tax overlay (§14 Addendum C): subtract a per-sleeve after-tax drag
    # from the ex-ante μ BEFORE the solve. The default ZeroTaxEstimator is an
    # identity (is_zero) → the overlay is skipped entirely so μ (and thus w*)
    # is byte-identical to the pre-overlay path; honesty #5 stays not_computed.
    if not getattr(estimator, "is_zero", False):
        drag = estimator.sleeve_mu_drag(universe, settings=cfg)
        mu = [
            mu[i] - float(drag.get(universe[i], Decimal("0")))
            for i in range(n)
        ]
    sigma = [
        [
            vols[i]
            * vols[j]
            * float(
                priors.pairwise_correlation(risk_classes[i], risk_classes[j])
            )
            for j in range(n)
        ]
        for i in range(n)
    ]

    unbounded: list[IpsSleeve] = []
    w_min: list[float] = []
    w_max: list[float] = []
    for sleeve in universe:
        target = target_by_class.get(sleeve)
        if target is None:
            # No IPS policy for this sleeve → free in [0, 1], flagged (§A.3).
            unbounded.append(sleeve)
            w_min.append(0.0)
            w_max.append(1.0)
        else:
            w_min.append(float(target.min_weight))
            w_max.append(float(target.max_weight))

    lam = float(cfg.risk_aversion_lambda)
    w_star_float = solve_qp(
        mu,
        sigma,
        w_min,
        w_max,
        lam=lam,
        tol=float(cfg.qp_tolerance),
        max_iters=int(cfg.qp_max_iters),
    )

    current_weights = {s: current.get(s, Decimal("0")) for s in universe}

    def _quantize_box(value: float | Decimal, i: int) -> Decimal:
        # 1) Clip float/Decimal dust into the box (avoids AllocationSlot
        # ge=0/le=1 raises), 2) quantize to Decimal (§A.2).
        clipped = min(
            max(Decimal(str(value)), Decimal(str(w_min[i]))),
            Decimal(str(w_max[i])),
        )
        return clipped.quantize(_QUANTUM, rounding=ROUND_HALF_EVEN)

    # po0 target — the unconstrained-by-turnover MV optimum w* (the raw QP
    # solve, clipped + quantized). When the IPS sets no turnover budget this is
    # the final target and every field below is byte-identical to po0.
    unconstrained_target: dict[IpsSleeve, Decimal] = {
        sleeve: _quantize_box(w_star_float[i], i)
        for i, sleeve in enumerate(universe)
    }
    unconstrained_turnover_l1 = sum(
        (abs(unconstrained_target[s] - current_weights[s]) for s in universe),
        Decimal("0"),
    )

    # po1 turnover budget (§B.3) — hard cap ‖Δw‖₁ ≤ τ. ROUTE B (first-cut
    # heuristic, documented): when the raw MV step over-trades, take the
    # budget-scaled convex step  w_budget = w_current + (τ/‖Δw‖₁)·(w* −
    # w_current). w_budget is a convex combination of w_current and w*, so it
    # stays inside the box ∩ simplex (Σw=1) and ‖w_budget − w_current‖₁ = τ
    # exactly (up to Decimal quantization). It is a feasible-DIRECTION step
    # toward the MV optimum, NOT the L1-constrained argmax — the constrained
    # optimum may lie off the segment. ROUTE A (Dykstra projection onto box ∩
    # simplex ∩ L1-ball) is the documented upgrade. ‖Δw‖₁ here is TWO-WAY
    # turnover (Σ|Δw| = buys + sells, since ΣΔw = 0); one-way = ‖Δw‖₁/2. The
    # budget is treated as a per-rebalance cap (the IPS field is labelled
    # "annual" — horizon mismatch flagged as a limitation, not silently
    # reconciled).
    turnover_budget = ips.turnover_budget_pct
    turnover_binding = False
    if (
        turnover_budget is not None
        and unconstrained_turnover_l1 > turnover_budget
    ):
        turnover_binding = True
        alpha = float(turnover_budget / unconstrained_turnover_l1)
        # Convex step toward w* in float, then PROJECT onto box ∩ simplex. On a
        # box-feasible w_current the step is already feasible (projection = id)
        # so ‖Δw‖₁ = τ exactly (up to quantization); when w_current breaches
        # the IPS box, the projection restores Σw=1/feasibility and turnover
        # can drift off τ — the honest box-vs-budget conflict (limitation).
        cur_f = [float(current_weights[s]) for s in universe]
        unc_f = [float(unconstrained_target[s]) for s in universe]
        step = [cur_f[i] + alpha * (unc_f[i] - cur_f[i]) for i in range(n)]
        projected = project_capped_simplex(step, w_min, w_max)
        target_weights = {
            sleeve: _quantize_box(projected[i], i)
            for i, sleeve in enumerate(universe)
        }
    else:
        target_weights = dict(unconstrained_target)

    # Re-assert Σw=1 (the AssetPortfolio sum validator is NOT in this path —
    # we build SleeveRiskState directly; §A.2).
    total = sum(target_weights.values(), Decimal("0"))
    if abs(total - Decimal("1")) > _SUM_TOLERANCE:
        raise OptimizerInfeasibleError(
            f"target weights sum to {total}, not 1 within {_SUM_TOLERANCE}; "
            "projection or quantization is wrong"
        )

    delta_w = {s: target_weights[s] - current_weights[s] for s in universe}
    turnover_l1 = sum((abs(d) for d in delta_w.values()), Decimal("0"))

    # policy_drift = w_current − IPS target_weight (0 if no target; §B.4).
    policy_drift: dict[IpsSleeve, Decimal] = {}
    for sleeve in universe:
        target = target_by_class.get(sleeve)
        if target is None:
            policy_drift[sleeve] = Decimal("0")
        else:
            policy_drift[sleeve] = (
                current_weights[sleeve] - target.target_weight
            )

    # Binding IPS bounds at w* — only sleeves with a real AllocationTarget
    # (legible/few — PM axiom 6).
    binding_bounds: list[str] = []
    for sleeve in universe:
        target = target_by_class.get(sleeve)
        if target is None:
            continue
        w = target_weights[sleeve]
        if abs(w - target.max_weight) <= _BIND_TOLERANCE:
            binding_bounds.append(f"ips_max:{sleeve.value}")
        elif abs(w - target.min_weight) <= _BIND_TOLERANCE:
            binding_bounds.append(f"ips_min:{sleeve.value}")

    # Illiquid flag is sleeve-level, not magnitude-gated (§B.5): the badge
    # fires even at Δw≈0 so the non-executable constraint is always visible.
    illiquid = (
        [IpsSleeve.ALTERNATIVES] if IpsSleeve.ALTERNATIVES in universe else []
    )

    # RC_i: call portfolio_covariance ONCE at w* (its real purpose here).
    states = [
        SleeveRiskState(
            slot=AllocationSlot(
                asset_class=risk_classes[i],
                weight=target_weights[universe[i]],
            ),
            annual_volatility=priors.class_annual_vol[risk_classes[i]],
            measurement="model_prior",
        )
        for i in range(n)
    ]
    cov = portfolio_covariance(states, priors)
    risk_contributions = {
        universe[i]: cov.pct_variance_contributions[i] for i in range(n)
    }

    # objective_value = w*ᵀμ − (λ/2)·w*ᵀΣw at the solve (reported, §B.2).
    w_vec = [float(target_weights[s]) for s in universe]
    quad = sum(
        w_vec[i] * sigma[i][j] * w_vec[j] for i in range(n) for j in range(n)
    )
    linear = sum(w_vec[i] * mu[i] for i in range(n))
    objective = linear - 0.5 * lam * quad

    # po2 scenario-robust stress overlay (§B.8 Option A) — a SECOND solve under
    # the crisis-regime Σ, reported alongside the base w*. Additive/advisory:
    # the base fields above are byte-identical regardless. compute_stress=False
    # on the inner re-solve breaks the recursion.
    stress_fields: dict[str, object] = {}
    if compute_stress:
        # Local import breaks the rebalance ⇆ robust import cycle.
        from warehouse.decision.optimizer.robust import compute_stress_overlay

        overlay = compute_stress_overlay(
            positions,
            ips,
            base_target_weights=target_weights,
            settings=cfg,
            stress_assumptions=stress_assumptions,
        )
        stress_fields = {
            "stress_regime": overlay.stress_regime,
            "stress_target_weights": overlay.stress_target_weights,
            "stress_delta_w": overlay.stress_delta_w,
            "regime_gap_l1": overlay.regime_gap_l1,
            "stress_objective_value": overlay.stress_objective_value,
            "stress_risk_contributions": overlay.stress_risk_contributions,
        }

    return RebalanceProposal(
        target_weights=target_weights,
        current_weights=current_weights,
        delta_w=delta_w,
        policy_drift=policy_drift,
        binding_bounds=binding_bounds,
        unbounded_sleeves=unbounded,
        illiquid_advisory_sleeves=illiquid,
        risk_contributions=risk_contributions,
        turnover_l1=turnover_l1,
        turnover_budget=turnover_budget,
        turnover_binding=turnover_binding,
        unconstrained_turnover_l1=unconstrained_turnover_l1,
        objective_value=Decimal(str(round(objective, 8))),
        lam=Decimal(str(cfg.risk_aversion_lambda)),
        config_version=cfg.optimizer_config_version,
        **stress_fields,
    )
