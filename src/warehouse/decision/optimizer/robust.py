"""Scenario-robust stress overlay (po2, §B.8 Option A) — PO7.

Base-regime MV optimizes on the normal-regime Σ, but correlations spike toward
1 in a crisis and the diversification benefit collapses exactly when it is
needed (PO7 non-stationarity; RM5 tails / RM6 factor independence breaks). po2
complements the base solve with a **second** constrained MV QP under a crisis
regime and reports the two target vectors side by side plus the regime gap
``‖w*_base − w*_stress‖₁``.

**Option A (shipped, §B.8 RECOMMENDED).** Re-solve the *same* QP under the
version-pinned ``high_risk`` regime — it reuses ``run_mv_rebalance`` (hence
``solve_qp`` / the Σ-build / the turnover-budget treatment) **verbatim** on an
alternate Σ, is the lightest route, and flips honesty matrix #8 cleanly. Option
C (scenario P&L via ``evaluate_stress`` over the ``STRESS_SCENARIOS``
return-shock packs) is the documented richer upgrade; Option B (a single
objective with a ``max_s w'Σ_s w`` penalty) is the alternative single-objective
form.

**Honest caveat (§B.8).** ``high_risk`` crisis-blends ρ toward 0.85 **and**
scales vols ×1.4 — it is a crisis *regime*, not a correlation-only shock. The
panel and docs say so; we do not imply "correlation-only".

Pure and advisory: this overlay stages **no trade** and persists nothing. μ
stays the **ex-ante class assumption**, never a forecast (PO6); the after-tax μ
overlay (honesty #5) is untouched and stays ``not_computed`` ($0 tax seam).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from warehouse.config import Settings
from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.ips import InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.research.risk.assumptions import RiskAssumptions
from warehouse.research.risk.scenarios import assumptions_for


class StressOverlay(BaseModel):
    """Result of the crisis-regime re-solve (§B.8 Option A) — advisory."""

    model_config = ConfigDict(frozen=True)

    stress_regime: str
    stress_target_weights: dict[IpsSleeve, Decimal]
    stress_delta_w: dict[IpsSleeve, Decimal]
    regime_gap_l1: Decimal
    stress_objective_value: Decimal
    stress_risk_contributions: dict[IpsSleeve, Decimal] = Field(
        default_factory=dict
    )


def compute_stress_overlay(
    positions: list[LotPositionView],
    ips: InvestmentPolicyStatement,
    *,
    base_target_weights: dict[IpsSleeve, Decimal],
    settings: Settings,
    stress_regime: str | None = None,
    stress_assumptions: RiskAssumptions | None = None,
) -> StressOverlay:
    """Re-solve the MV QP under a crisis Σ; report the base-vs-stress gap.

    Reuses ``run_mv_rebalance`` on the crisis priors (``solve_qp`` / Σ-build /
    turnover treatment verbatim) with ``compute_stress=False`` to break the
    recursion. ``stress_assumptions`` overrides the regime priors (tests inject
    a controlled high-ρ Σ); otherwise the version-pinned ``stress_regime``
    (default ``settings.optimizer_stress_regime``, i.e. ``high_risk``) is used.

    Edge cases bubble — an infeasible crisis box or a failed Σw=1 re-assertion
    raises out of the inner solve (no silent fallback, no default-on-failure).
    """
    # Local import breaks the rebalance ⇆ robust import cycle.
    from warehouse.decision.optimizer.rebalance import run_mv_rebalance

    regime = stress_regime or settings.optimizer_stress_regime
    priors = stress_assumptions or assumptions_for(regime)

    stress = run_mv_rebalance(
        positions,
        ips,
        assumptions=priors,
        settings=settings,
        compute_stress=False,
    )

    stress_target = stress.target_weights
    sleeves = list(base_target_weights) + [
        s for s in stress_target if s not in base_target_weights
    ]
    stress_delta_w = {
        s: stress_target.get(s, Decimal("0"))
        - base_target_weights.get(s, Decimal("0"))
        for s in sleeves
    }
    regime_gap_l1 = sum(
        (abs(d) for d in stress_delta_w.values()), Decimal("0")
    )

    return StressOverlay(
        stress_regime=regime,
        stress_target_weights=stress_target,
        stress_delta_w=stress_delta_w,
        regime_gap_l1=regime_gap_l1,
        stress_objective_value=stress.objective_value,
        stress_risk_contributions=stress.risk_contributions,
    )
