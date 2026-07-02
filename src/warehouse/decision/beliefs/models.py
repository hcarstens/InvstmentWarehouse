"""Bayesian belief records (pv1) — frozen + registered from day one.

Every belief record is audit/replay-critical: a Black–Litterman posterior is a
**replay fingerprint** (prior ⊕ views → versioned posterior), so all four types
are ``frozen=True`` and appended to
``warehouse.integrity.frozen_registry.FROZEN_TYPES`` in this slice (the review
M1/M2 fix, done right rather than retrofitted).

Honesty rule (pm/po house rule; the Goodhart guard): a ``View`` is
``manual``/demo only in pv1 (FIIJ ingest is pv2), its ``calibration`` stays
``not_computed`` until a scored history exists, and the prior is labelled an
ex-ante **class assumption**, never a reverse-optimized equilibrium. We never
fabricate alpha or a confidence the input does not support.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from warehouse.decision.ips.sleeves import IpsSleeve


class SingularCovarianceError(ValueError):
    """Prior covariance Σ (or the BL posterior-precision) is singular.

    Raised instead of silently falling back to a pseudo-inverse — a singular
    Σ means the sleeve block is degenerate and the blend is undefined; errors
    bubble to the surface (CLAUDE.md), never a quiet ``pinv``.
    """


class ViewMappingError(ValueError):
    """A view references a sleeve outside the book's sleeve universe.

    Never a silent drop — a view the engine cannot place on a sleeve is a loud
    failure (mirrors the optimizer's ``OptimizerMappingError`` discipline).
    """


class ViewSource(StrEnum):
    """Where a view came from — labelled so demo is never dressed as signal."""

    MANUAL = "manual"  # discretionary / demo — pv1 only
    FIIJ = "fiij"  # ingested FIIJ finance-view signal — pv2+
    STAT_MOVE = "stat_move"  # z-score evidence from our own stats.daily (pv3)


class View(BaseModel):
    """A confidence-weighted statement about a sleeve's excess return.

    ``expected_excess`` is a tilt **vs the prior** (the BL view target is
    ``prior_mu[sleeve] + expected_excess``); ``confidence`` ∈ [0, 1] is the
    source of the BL Ω diagonal (higher confidence → tighter Ω → the posterior
    moves further toward the view). ``calibration`` is ``not_computed`` until a
    scored OOS history exists (#8).
    """

    model_config = ConfigDict(frozen=True)

    sleeve: IpsSleeve
    expected_excess: Decimal
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    source: ViewSource
    source_ref: str | None = None
    calibration: str = "not_computed"
    rationale: str


class PriorBelief(BaseModel):
    """The prior μ — v0 = shipped ex-ante class assumption (not equilib.)."""

    model_config = ConfigDict(frozen=True)

    mu: dict[IpsSleeve, Decimal]
    prior_source: str = "class_assumption"
    assumptions_version: str


class PosteriorBelief(BaseModel):
    """The BL-blended posterior μ fed into the po0 QP as its μ input."""

    model_config = ConfigDict(frozen=True)

    mu: dict[IpsSleeve, Decimal]
    method: str = "black_litterman"
    tau: Decimal


class BeliefUpdate(BaseModel):
    """The belief-journal entry / replay fingerprint (prior ⊕ views → post.).

    ``views`` is a ``tuple`` (hashable, immutable — not a list).
    ``calibration`` stays ``not_computed`` until the journal accrues a
    realized-vs-forecast history to score against (F8 honesty).
    """

    model_config = ConfigDict(frozen=True)

    correlation_id: str
    as_of_date: date
    prior: PriorBelief
    views: tuple[View, ...]
    posterior: PosteriorBelief
    belief_config_version: str
    calibration: str = "not_computed"
