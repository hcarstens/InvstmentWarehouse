"""pm0 — PM narrative, axiom scoring, specialist liveness."""

from collections.abc import Iterator
from decimal import Decimal

import pytest

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.decision.pm import (
    build_working_set,
    build_working_set_from_bundle,
    score_pm_axioms,
)
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging import (
    REGISTRY,
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
    observability,
)
from warehouse.messaging.payloads import AdviceBundle, AxiomScore
from warehouse.research.synthetic import emit_synthetic_household

DEMO = DEMO_HOUSEHOLD_ID


@pytest.fixture
def seeded() -> Iterator[None]:
    bootstrap_database(seed=True)
    yield


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    snapshot = dict(REGISTRY)
    observability.clear()
    yield
    REGISTRY.clear()
    REGISTRY.update(snapshot)
    observability.clear()


def _demo_advise(seeded: None) -> AdviceBundle:
    with session_scope() as s:
        payload = build_working_set(s, DEMO)
    ctx = DispatchContext(session=None)  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="pm.advise",
            kind=Kind.EVALUATE,
            payload=payload,
            correlation_id="pm-narrative-test",
            household_id=DEMO,
        ),
    )
    assert isinstance(out, AdviceBundle)
    return out


def test_pm_advise_attaches_narrative(seeded: None) -> None:
    bundle = _demo_advise(seeded)
    assert bundle.narrative is not None
    assert bundle.narrative.correlation_id == "pm-narrative-test"
    assert bundle.narrative.headline


def test_specialist_status_honest(seeded: None) -> None:
    narrative = _demo_advise(seeded).narrative
    assert narrative is not None
    status = narrative.specialist_status
    assert status["tax"] == "stub"
    assert status["risk"] == "live"
    assert status["analyst"] == "live"
    assert status["optimizer"] == "live"


def test_axiom5_not_computed(seeded: None) -> None:
    narrative = _demo_advise(seeded).narrative
    assert narrative is not None
    assert narrative.axioms_scored["axiom_5"] == AxiomScore.NOT_COMPUTED


def test_axiom_scores_measurable(seeded: None) -> None:
    narrative = _demo_advise(seeded).narrative
    assert narrative is not None
    scored = narrative.axioms_scored
    assert len(scored) == 7
    measurable = sum(
        1
        for s in scored.values()
        if s in (AxiomScore.PASS, AxiomScore.WARN, AxiomScore.BREACH)
    )
    assert measurable >= 6


def test_tax_scenario_stub_zero(seeded: None) -> None:
    bundle = _demo_advise(seeded)
    assert bundle.tax.baseline_tax == Decimal("0")
    assert bundle.tax.scenario_tax == Decimal("0")
    assert bundle.tax.tax_delta == Decimal("0")


def test_axiom2_breaches_on_concentration(seeded: None) -> None:
    """Effective-bets axiom must fail a variance-concentrated book.

    Regression for the scale bug where pct_variance_contribution (a
    [0,1] fraction) was divided by 100, inflating effective bets ~100x
    so axiom 2 always PASSed regardless of concentration.
    """
    bundle = _demo_advise(seeded)
    contribs = bundle.risk.report.level_2_contributions.by_class
    hhi = sum(float(c.pct_variance_contribution) ** 2 for c in contribs)
    effective_bets = 1.0 / hhi
    # Demo book is variance-concentrated (~1.3 effective bets).
    assert effective_bets < 2.0
    assert bundle.narrative is not None
    assert bundle.narrative.axioms_scored["axiom_2"] in (
        AxiomScore.WARN,
        AxiomScore.BREACH,
    )


def test_score_pm_axioms_direct(seeded: None) -> None:
    bundle = _demo_advise(seeded)
    payload = build_working_set_from_bundle(
        emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    )
    narrative = score_pm_axioms(bundle, payload, correlation_id="direct-score")
    assert narrative.axioms_scored["axiom_5"] == AxiomScore.NOT_COMPUTED
