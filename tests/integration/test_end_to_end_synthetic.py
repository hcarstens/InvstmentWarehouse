"""End-to-end integration — generated portfolio + IPS through every plane.

Generates a household per cohort (positions + IPS via the synthetic
generators) and drives the whole stack in-process (no DB): policy drift, v0
TLH, optimizer v1 (po0/po1/po2 MV-QP + scenario-robust stress), scenario card,
and the ``pm.advise`` coordinator. Asserts the cross-cutting invariants hold on
generated data — not just the curated demo fixture.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.decision.pm import build_working_set_from_bundle
from warehouse.messaging import (
    REGISTRY,
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
    observability,
)
from warehouse.messaging.payloads import AdviceBundle, PmAdvisePayload
from warehouse.research.synthetic import (
    emit_synthetic_household,
    run_e2e_matrix,
    run_workflow_smoke,
)

_SUM_TOL = Decimal("0.0001")

# (cohort, rung, seed) — one representative household per cohort.
_COMBOS = [
    ("general_hnw", 3, 42),
    ("uhnw_inherited", 3, 42),
    ("founder_executive", 3, 42),
    ("concentrated_stress", 4, 42),
]


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    snapshot = dict(REGISTRY)
    observability.clear()
    yield
    REGISTRY.clear()
    REGISTRY.update(snapshot)
    observability.clear()


@pytest.mark.parametrize(("cohort", "rung", "seed"), _COMBOS)
def test_pm_advise_full_stack_on_generated_household(
    cohort: str, rung: int, seed: int
) -> None:
    """Generated portfolio + IPS → pm.advise carries every leg, tax $0."""
    bundle = emit_synthetic_household(
        cohort_id=cohort, seed=seed, rung=rung, validate=False
    )
    payload = build_working_set_from_bundle(bundle)
    ctx = DispatchContext(session=None)  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="pm.advise",
            kind=Kind.EVALUATE,
            payload=PmAdvisePayload.model_validate(payload.model_dump()),
            correlation_id=f"e2e-{cohort}",
            household_id=payload.household_id,
        ),
    )
    assert isinstance(out, AdviceBundle)
    # Every leg present.
    assert out.risk.report is not None
    assert out.drift is not None
    assert out.narrative is not None
    assert out.proposal.rebalance is not None
    # Tax leg held at $0 — honesty #5 stays not_computed (seam wired only).
    assert out.tax.tax_delta == Decimal("0")


@pytest.mark.parametrize(("cohort", "rung", "seed"), _COMBOS)
def test_mv_qp_invariants_on_generated_household(
    cohort: str, rung: int, seed: int
) -> None:
    """Optimizer v1 invariants on generated data: Σw*=1, stress overlay ran."""
    bundle = emit_synthetic_household(
        cohort_id=cohort, seed=seed, rung=rung, validate=False
    )
    from warehouse.decision.optimizer.rebalance import run_mv_rebalance
    from warehouse.research.synthetic.fixture_views import (
        lot_positions_from_fixture,
    )

    restricted = frozenset(bundle.ips.restricted_securities)
    positions = lot_positions_from_fixture(
        bundle.fixture, restricted_tickers=restricted
    )
    proposal = run_mv_rebalance(positions, bundle.ips)
    # Σw* = 1, box-feasible.
    total = sum(proposal.target_weights.values(), Decimal("0"))
    assert abs(total - Decimal("1")) <= _SUM_TOL
    for w in proposal.target_weights.values():
        assert Decimal("0") <= w <= Decimal("1")
    # po2 scenario-robust overlay genuinely ran (second crisis-Σ solve).
    assert proposal.stress_regime == "high_risk"
    assert proposal.regime_gap_l1 >= Decimal("0")
    # μ honesty preserved; no trade staged from the QP path.
    assert proposal.mu_source == "ex_ante_class_assumption"
    assert not hasattr(proposal, "trades")


def test_workflow_smoke_includes_v1_and_pm_legs() -> None:
    """run_workflow_smoke now exercises the MV-QP and pm.advise legs."""
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    result = run_workflow_smoke(bundle)
    workflows = {c.workflow for c in result.checks}
    assert "mv_rebalance_qp" in workflows
    assert "pm_advise" in workflows
    # Every leg passes on the canonical interior fixture.
    assert result.ok, [c.detail for c in result.checks if not c.ok]


def test_e2e_matrix_all_cohorts_green() -> None:
    """The full cohort×rung matrix passes every leg end-to-end."""
    matrix = run_e2e_matrix()
    assert matrix.summary["households"] == len(_COMBOS)
    failed = [
        (r.cohort_id, c.workflow, c.detail)
        for r in matrix.results
        for c in r.checks
        if not c.ok
    ]
    assert matrix.ok, failed


def test_e2e_matrix_deterministic() -> None:
    """Same seeds → identical optimizer targets (audit replay)."""
    first = run_e2e_matrix()
    second = run_e2e_matrix()
    first_details = [
        (r.cohort_id, c.workflow, c.detail)
        for r in first.results
        for c in r.checks
    ]
    second_details = [
        (r.cohort_id, c.workflow, c.detail)
        for r in second.results
        for c in r.checks
    ]
    assert first_details == second_details
