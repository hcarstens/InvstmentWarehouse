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
from warehouse.decision.optimizer.qp import solve_qp
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
) -> RebalanceProposal:
    """Constrained MV QP over sleeve weights → advisory ``RebalanceProposal``.

    Walk-forward safe: Σ/μ are the as-of base-regime priors; no realized-return
    lookahead (CLAUDE.md). Raises ``OptimizerMappingError`` on an unmapped
    sleeve and ``OptimizerInfeasibleError`` on an empty box∩simplex.
    """
    cfg = settings or get_settings()
    priors = assumptions or assumptions_for("base")

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

    # 1) Clip float dust into the box (avoids AllocationSlot ge=0/le=1 raises),
    # 2) quantize to Decimal, 3) re-assert Σw=1 (the AssetPortfolio sum
    # validator is NOT in this path — we build SleeveRiskState directly; §A.2).
    target_weights: dict[IpsSleeve, Decimal] = {}
    quantized: list[Decimal] = []
    for i, sleeve in enumerate(universe):
        clipped = min(max(w_star_float[i], w_min[i]), w_max[i])
        q = Decimal(str(clipped)).quantize(_QUANTUM, rounding=ROUND_HALF_EVEN)
        target_weights[sleeve] = q
        quantized.append(q)

    total = sum(quantized, Decimal("0"))
    if abs(total - Decimal("1")) > _SUM_TOLERANCE:
        raise OptimizerInfeasibleError(
            f"target weights sum to {total}, not 1 within {_SUM_TOLERANCE}; "
            "projection or quantization is wrong"
        )

    current_weights = {s: current.get(s, Decimal("0")) for s in universe}
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
        objective_value=Decimal(str(round(objective, 8))),
        lam=Decimal(str(cfg.risk_aversion_lambda)),
        config_version=cfg.optimizer_config_version,
    )
