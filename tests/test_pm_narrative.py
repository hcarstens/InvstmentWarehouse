"""pm0 — PM narrative, axiom scoring, specialist liveness."""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.analyst import (
    AnalystCheckpointScore,
    risk_class_for,
    score_analyst_checkpoints,
)
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
from warehouse.messaging.payloads import (
    AdviceBundle,
    AxiomScore,
    PmAdvisePayload,
)
from warehouse.research.risk.scenarios import assumptions_for
from warehouse.research.synthetic import emit_synthetic_household

DEMO = DEMO_HOUSEHOLD_ID
_ONE = Decimal("1")
_QUANTUM = Decimal("0.000001")
# Tolerance for re-deriving expected_cumulative via the oracle. The production
# path and this test's (1+r)**years recomputation round independently, so the
# two can differ by a few quanta (interpreter/Decimal-context dependent) — a
# logic error would be orders of magnitude larger. Keep _QUANTUM for the exact
# algebraic identity (recombination) below.
_ORACLE_TOL = Decimal("0.00001")


def _oracle_expected_cumulative(
    class_expected: Decimal,
    holding_years: Decimal,
) -> Decimal:
    return (_ONE + class_expected) ** holding_years - _ONE


def _oracle_active_return(
    total_return: Decimal,
    expected_cumulative: Decimal,
) -> Decimal:
    return total_return - expected_cumulative


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


def test_pm_attribution_oracle_on_hnw_path() -> None:
    """PM nest-dispatch: each lot decomposes with independent oracle (ST2)."""
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    payload = build_working_set_from_bundle(bundle)
    ctx = DispatchContext(session=None)  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="pm.advise",
            kind=Kind.EVALUATE,
            payload=PmAdvisePayload.model_validate(payload.model_dump()),
            correlation_id="hnw-oracle",
            household_id=payload.household_id,
        ),
    )
    assert out.attribution is not None
    for pa in out.attribution.positions:
        if pa.holding_years <= 0:
            continue
        recombined = pa.expected_cumulative + pa.active_return
        assert abs(recombined - pa.total_return) <= _QUANTUM
        expected = _oracle_expected_cumulative(
            pa.class_expected,
            pa.holding_years,
        ).quantize(_QUANTUM)
        assert abs(pa.expected_cumulative - expected) <= _ORACLE_TOL


def test_pm_zero_residual_probe_checkpoint_pass() -> None:
    """§9 zero-residual probe — class-par lot → checkpoint 2 PASS via PM."""
    eq_exp = assumptions_for("base").class_expected_return[
        risk_class_for(SecClass.EQUITY)
    ]
    cost = Decimal("100")
    mv = cost * (_ONE + eq_exp)
    lot = LotPositionView(
        lot_id="probe",
        account_id="acct",
        account_name="Account",
        security_id="VTI",
        ticker="VTI",
        security_name="VTI",
        security_asset_class=SecClass.EQUITY,
        liquidity_tier=1,
        quantity=Decimal("1"),
        cost_basis_per_share=cost,
        total_cost_basis=cost,
        market_price=mv,
        market_value=mv,
        unrealized_gain=mv - cost,
        acquisition_date=date(2025, 6, 28),
        is_restricted=False,
        wash_sale_substitute_group=None,
    )
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    payload = build_working_set_from_bundle(bundle)
    payload = payload.model_copy(update={"positions": [lot]})
    ctx = DispatchContext(session=None)  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="pm.advise",
            kind=Kind.EVALUATE,
            payload=PmAdvisePayload.model_validate(payload.model_dump()),
            correlation_id="zero-residual",
            household_id=payload.household_id,
        ),
    )
    assert out.attribution is not None
    pa = out.attribution.positions[0]
    assert abs(pa.active_return) < Decimal("0.01")
    review = score_analyst_checkpoints(out.attribution)
    assert review.checkpoints["checkpoint_2"] == AnalystCheckpointScore.PASS
