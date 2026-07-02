"""Bayesian belief engine (pv1) — Black–Litterman posterior over the book.

The daily PM loop's "update" step (ℍ_Allocation axiom 7 — rebalance on
calibrated evidence): a **prior** μ (the shipped ex-ante class assumption) is
blended with confidence-weighted **views** into a **posterior** μ, recorded as
an immutable ``BeliefUpdate`` journal entry, and fed into the shipped po0 QP as
its μ input — a **caller change only** (``run_mv_rebalance`` is untouched; S1
reuse discipline). No new market data: the prior is the version-pinned μ.

Pure and advisory: every function here mutates nothing and stages no trade
(the human approval gate dominates). μ is an ex-ante class assumption, never a
forecast (PO6); views are ``manual``/demo in pv1 (FIIJ is pv2).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from warehouse.config import Settings, get_settings
from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.beliefs.black_litterman import black_litterman
from warehouse.decision.beliefs.models import (
    BeliefUpdate,
    PosteriorBelief,
    PriorBelief,
    SingularCovarianceError,
    View,
    ViewMappingError,
    ViewSource,
)
from warehouse.decision.ips import InvestmentPolicyStatement
from warehouse.decision.ips.rollup import ips_sleeve_for_position
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.optimizer.models import RebalanceProposal
from warehouse.decision.optimizer.rebalance import (
    risk_class_for,
    run_mv_rebalance,
)
from warehouse.research.risk.assumptions import RiskAssumptions
from warehouse.research.risk.scenarios import assumptions_for

if TYPE_CHECKING:  # avoid an import cycle with messaging.payloads (Book).
    from warehouse.messaging.payloads import PmAdvisePayload

__all__ = [
    "BeliefUpdate",
    "PosteriorBelief",
    "PriorBelief",
    "SingularCovarianceError",
    "View",
    "ViewMappingError",
    "ViewSource",
    "black_litterman",
    "rebalance_on_posterior",
    "update_beliefs",
]


def _sleeve_universe(
    positions: list[LotPositionView],
    ips: InvestmentPolicyStatement,
) -> list[IpsSleeve]:
    """Book sleeve universe = positions ∪ IPS targets (po0 canonical order).

    Identical to ``run_mv_rebalance``'s universe so the posterior μ lines up
    with the QP's μ lookup sleeve-for-sleeve.
    """
    present = {
        ips_sleeve_for_position(p)
        for p in positions
        if p.market_value is not None
    }
    present |= {t.asset_class for t in ips.allocation_targets}
    return [s for s in IpsSleeve if s in present]


def build_prior(
    positions: list[LotPositionView],
    ips: InvestmentPolicyStatement,
    *,
    assumptions: RiskAssumptions | None = None,
) -> PriorBelief:
    """Prior μ = the shipped ``class_expected_return`` (labelled assumption).

    Labelled ``class_assumption`` — an ex-ante class prior, NOT a reverse-
    optimized equilibrium (the honest v0 limitation; #10).
    """
    priors = assumptions or assumptions_for("base")
    universe = _sleeve_universe(positions, ips)
    mu = {
        sleeve: priors.class_expected_return[risk_class_for(sleeve)]
        for sleeve in universe
    }
    return PriorBelief(
        mu=mu,
        prior_source="class_assumption",
        assumptions_version=priors.model_version,
    )


def _build_sigma(
    universe: list[IpsSleeve], priors: RiskAssumptions
) -> list[list[float]]:
    """Σ over the sleeve block — the exact po0 §A cov[i][j] formula (float)."""
    risk_classes = [risk_class_for(s) for s in universe]
    vols = [float(priors.class_annual_vol[rc]) for rc in risk_classes]
    n = len(universe)
    return [
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


def update_beliefs(
    book: PmAdvisePayload,
    views: tuple[View, ...],
    *,
    correlation_id: str = "",
    as_of_date: date | None = None,
    settings: Settings | None = None,
) -> BeliefUpdate:
    """Blend the book's prior μ with ``views`` → an immutable ``BeliefUpdate``.

    Pure: reads the passed book, mutates nothing, persists nothing (mirrors
    ``pm.advise``). Raises ``SingularCovarianceError`` on a degenerate Σ and
    ``ViewMappingError`` on a view outside the book's sleeve universe — no
    silent fallback.
    """
    cfg = settings or get_settings()
    priors = assumptions_for("base")
    prior = build_prior(book.positions, book.ips, assumptions=priors)
    universe = list(prior.mu.keys())
    sigma = _build_sigma(universe, priors)
    posterior = black_litterman(
        prior.mu,
        sigma,
        views,
        tau=Decimal(str(cfg.black_litterman_tau)),
        settings=cfg,
    )
    return BeliefUpdate(
        correlation_id=correlation_id,
        as_of_date=as_of_date or book.as_of_date or date.today(),
        prior=prior,
        views=views,
        posterior=posterior,
        belief_config_version=cfg.belief_config_version,
    )


def rebalance_on_posterior(
    book: PmAdvisePayload,
    posterior: PosteriorBelief,
    *,
    settings: Settings | None = None,
    compute_stress: bool = False,
) -> RebalanceProposal:
    """Feed the posterior μ into the po0 QP — **caller change only**.

    The QP (``run_mv_rebalance``) is untouched (S1): we hand it a
    ``RiskAssumptions`` whose ``class_expected_return`` is overridden by the
    posterior μ over the book's sleeve universe, so the optimizer sees the
    Bayesian μ without any engine change. Zero-view posterior == prior μ →
    the assumptions equal the base priors → w* is the po0 baseline (identity).
    """
    cfg = settings or get_settings()
    priors = assumptions_for("base")
    new_cer = dict(priors.class_expected_return)
    for sleeve, value in posterior.mu.items():
        new_cer[risk_class_for(sleeve)] = value
    posterior_priors = replace(priors, class_expected_return=new_cer)
    return run_mv_rebalance(
        book.positions,
        book.ips,
        assumptions=posterior_priors,
        settings=cfg,
        compute_stress=compute_stress,
    )
