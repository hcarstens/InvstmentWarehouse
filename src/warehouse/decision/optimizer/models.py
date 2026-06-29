"""Portfolio Optimization v1 (po0) — rebalance proposal + errors.

The constrained mean-variance QP is **pure and advisory** (impl plan §1): it
produces a target sleeve-weight vector w*, the rebalance Δw, binding IPS
bounds, and per-sleeve risk contributions — it **never stages a trade and
never auto-executes** (CLAUDE.md human gate). Canonical field set per §B.2.

``RebalanceProposal`` is audit/replay-critical → frozen + version-pinned;
registered in ``warehouse.integrity.frozen_registry`` (§4).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from warehouse.decision.ips.sleeves import IpsSleeve


class OptimizerMappingError(ValueError):
    """No risk-class analog for a sleeve — never a silent zero-μ (§A.1).

    ``IpsSleeve`` and ``research.risk.AssetClass`` are value-identical
    ``StrEnum``s, so a naive ``class_expected_return[sleeve]`` join *silently
    succeeds* and would mis-price μ/Σ the instant either enum drifts. The
    explicit raising ``_SLEEVE_TO_RISK`` map turns that into a loud failure.
    """


class OptimizerInfeasibleError(ValueError):
    """Box ∩ simplex is empty, or w* failed the Σw=1 re-assertion (§A.2/A.3).

    Raised *before* the solve when ``Σ w_min > 1`` or ``Σ w_max < 1`` (no
    silent clip), and after quantization if the target weights do not sum to 1
    within tolerance (the projection or quantization is wrong).
    """


class RebalanceProposal(BaseModel):
    """Advisory constrained-MV target — w*/Δw/RC, no trade (§B.2).

    All components are always present (empty collections where noted); μ is an
    **ex-ante class assumption**, never a forecast/alpha (PO6 honesty).
    """

    model_config = ConfigDict(frozen=True)

    target_weights: dict[IpsSleeve, Decimal]
    current_weights: dict[IpsSleeve, Decimal]
    delta_w: dict[IpsSleeve, Decimal]
    policy_drift: dict[IpsSleeve, Decimal]
    binding_bounds: list[str] = Field(default_factory=list)
    unbounded_sleeves: list[IpsSleeve] = Field(default_factory=list)
    illiquid_advisory_sleeves: list[IpsSleeve] = Field(default_factory=list)
    risk_contributions: dict[IpsSleeve, Decimal]
    turnover_l1: Decimal
    # Turnover budget τ (po1, §B.3): the hard ‖Δw‖₁ ≤ τ cap. ``None`` when
    # the IPS sets no ``turnover_budget_pct`` → po1 is a no-op and every field
    # above is byte-identical to po0. ``unconstrained_turnover_l1`` is the
    # pre-cap Σ|Δw| of the raw MV optimum (the "capped from X to τ" story);
    # ``turnover_binding`` records whether the cap actually engaged.
    turnover_budget: Decimal | None = None
    turnover_binding: bool = False
    unconstrained_turnover_l1: Decimal = Decimal("0")
    objective_value: Decimal
    mu_source: Literal["ex_ante_class_assumption"] = "ex_ante_class_assumption"
    lam: Decimal
    config_version: str
    # po2 scenario-robust stress overlay (§B.8, Option A) — additive, advisory.
    # A SECOND solve re-runs the constrained MV QP under a crisis-regime Σ
    # (default the version-pinned ``high_risk`` regime: ρ crisis-blended toward
    # 0.85 AND vols ×1.4 — a crisis *regime*, not a correlation-only shock).
    # ``stress_regime`` is ``None`` when the overlay was not computed → every
    # field above is byte-identical to po1. ``stress_delta_w`` is the
    # per-sleeve regime shift vs base-MV w* (w*_stress − w*_base);
    # ``regime_gap_l1`` is its L1 norm ‖w*_base − w*_stress‖₁ (PO7 — how far
    # the crisis optimum moves off the base optimum). On bound-determined
    # fixtures both optima are bound-pinned → the gap is ~0 (honest, not
    # faked).
    stress_regime: str | None = None
    stress_target_weights: dict[IpsSleeve, Decimal] = Field(
        default_factory=dict
    )
    stress_delta_w: dict[IpsSleeve, Decimal] = Field(default_factory=dict)
    regime_gap_l1: Decimal = Decimal("0")
    stress_objective_value: Decimal = Decimal("0")
    stress_risk_contributions: dict[IpsSleeve, Decimal] = Field(
        default_factory=dict
    )
