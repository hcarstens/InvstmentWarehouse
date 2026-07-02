"""Belief Journal panel data (pv1) — real belief-engine output.

Thin loader (M4 — engines live in-plane, the dashboard only consumes): emit an
in-process ``general_hnw`` rung-3 book (no DB, §8), attach a demo ``manual``
view, run the Black–Litterman blend (``update_beliefs``), and report the
belief journal — prior μ → views → posterior μ → resulting w* vs the pre-view
(zero-view) baseline w*.

Honest by construction: the view is ``manual``/demo (FIIJ ingest is pv2), its
``calibration`` is ``not_computed``, and the prior is labelled an ex-ante class
assumption, not an equilibrium (#10). The loop is advisory — w*/Δw are
proposals, nothing is staged (human gate). Failures surface in ``error``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from warehouse.decision.beliefs import (
    View,
    ViewSource,
    rebalance_on_posterior,
    update_beliefs,
)
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.optimizer.rebalance import run_mv_rebalance
from warehouse.decision.pm import build_working_set_from_bundle
from warehouse.research.synthetic import emit_synthetic_household
from warehouse.research.synthetic.fixture_views import smoke_as_of_date

_BELIEF_COHORT = "general_hnw"
_BELIEF_SEED = 42
_BELIEF_RUNG = 3

# Honesty label (PO6 / #10): the prior is an ex-ante class assumption, never a
# reverse-optimized equilibrium. Rendered verbatim; scanned by the panel test.
PRIOR_SOURCE_LABEL = "ex-ante class assumption (not equilibrium)"

# Demo view (pv1): a discretionary manual equity tilt — labelled `manual`, its
# calibration `not_computed`. It exercises the directional + w* legs of the
# panel without fabricating a signal (FIIJ signal views arrive in pv2).
_DEMO_VIEW_SLEEVE = IpsSleeve.EQUITY
_DEMO_VIEW_EXCESS = Decimal("0.03")
_DEMO_VIEW_CONFIDENCE = Decimal("0.6")


class BeliefViewRow(BaseModel):
    sleeve: str
    expected_excess: Decimal
    confidence: Decimal
    source: str
    calibration: str
    rationale: str


class BeliefSleeveRow(BaseModel):
    sleeve: str
    prior_mu: Decimal
    posterior_mu: Decimal
    mu_delta: Decimal
    baseline_weight: Decimal  # pre-view w* (zero-view baseline)
    posterior_weight: Decimal  # w* on the posterior μ
    weight_delta: Decimal


class BeliefJournalData(BaseModel):
    household_id: str
    cohort_id: str
    as_of_date: date
    correlation_id: str
    method: str
    tau: Decimal
    prior_source: str
    prior_source_label: str
    assumptions_version: str
    belief_config_version: str
    calibration: str
    views: list[BeliefViewRow]
    rows: list[BeliefSleeveRow]
    panel_status: str = "live"
    error: str | None = None


def load_beliefs_dashboard() -> BeliefJournalData:
    try:
        bundle = emit_synthetic_household(
            cohort_id=_BELIEF_COHORT,
            seed=_BELIEF_SEED,
            rung=_BELIEF_RUNG,
        )
        as_of = smoke_as_of_date(bundle.fixture)
        book = build_working_set_from_bundle(bundle, as_of_date=as_of)

        views = (
            View(
                sleeve=_DEMO_VIEW_SLEEVE,
                expected_excess=_DEMO_VIEW_EXCESS,
                confidence=_DEMO_VIEW_CONFIDENCE,
                source=ViewSource.MANUAL,
                rationale=(
                    "demo manual tilt — discretionary equity view (pv1); "
                    "no signal fabricated"
                ),
            ),
        )
        belief = update_beliefs(
            book, views, correlation_id="belief-journal-demo", as_of_date=as_of
        )

        # w* on the posterior μ vs the pre-view (zero-view) baseline w* — the
        # caller change only; the QP is untouched.
        baseline = run_mv_rebalance(
            book.positions, book.ips, compute_stress=False
        )
        posterior_rebal = rebalance_on_posterior(
            book, belief.posterior, compute_stress=False
        )

        zero = Decimal("0")
        rows = [
            BeliefSleeveRow(
                sleeve=sleeve.value,
                prior_mu=belief.prior.mu[sleeve],
                posterior_mu=belief.posterior.mu[sleeve],
                mu_delta=(
                    belief.posterior.mu[sleeve] - belief.prior.mu[sleeve]
                ),
                baseline_weight=baseline.target_weights.get(sleeve, zero),
                posterior_weight=posterior_rebal.target_weights.get(
                    sleeve, zero
                ),
                weight_delta=(
                    posterior_rebal.target_weights.get(sleeve, zero)
                    - baseline.target_weights.get(sleeve, zero)
                ),
            )
            for sleeve in belief.prior.mu
        ]
        view_rows = [
            BeliefViewRow(
                sleeve=v.sleeve.value,
                expected_excess=v.expected_excess,
                confidence=v.confidence,
                source=v.source.value,
                calibration=v.calibration,
                rationale=v.rationale,
            )
            for v in belief.views
        ]
        return BeliefJournalData(
            household_id=book.household_id,
            cohort_id=_BELIEF_COHORT,
            as_of_date=as_of,
            correlation_id=belief.correlation_id,
            method=belief.posterior.method,
            tau=belief.posterior.tau,
            prior_source=belief.prior.prior_source,
            prior_source_label=PRIOR_SOURCE_LABEL,
            assumptions_version=belief.prior.assumptions_version,
            belief_config_version=belief.belief_config_version,
            calibration=belief.calibration,
            views=view_rows,
            rows=rows,
        )
    except Exception as err:
        return BeliefJournalData(
            household_id="(unavailable)",
            cohort_id=_BELIEF_COHORT,
            as_of_date=date.today(),
            correlation_id="(unavailable)",
            method="black_litterman",
            tau=Decimal("0"),
            prior_source="class_assumption",
            prior_source_label=PRIOR_SOURCE_LABEL,
            assumptions_version="(unavailable)",
            belief_config_version="(unavailable)",
            calibration="not_computed",
            views=[],
            rows=[],
            panel_status="error",
            error=str(err),
        )
