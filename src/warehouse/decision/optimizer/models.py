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
    objective_value: Decimal
    mu_source: Literal["ex_ante_class_assumption"] = "ex_ante_class_assumption"
    lam: Decimal
    config_version: str
