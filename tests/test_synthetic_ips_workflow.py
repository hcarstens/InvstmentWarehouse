"""Synthetic IPS workflow smokes — si3 SDG3 matrix."""

from __future__ import annotations

import pytest

from warehouse.decision.ips.monitor import build_ips_drift_report_from_views
from warehouse.research.synthetic import COHORT_IDS, emit_synthetic_household
from warehouse.research.synthetic.fixture_views import (
    lot_positions_from_fixture,
)
from warehouse.research.synthetic.scenario_card import build_scenario_card
from warehouse.research.synthetic.workflow_smoke import run_workflow_smoke


@pytest.mark.parametrize("cohort_id", COHORT_IDS)
def test_workflow_smoke_passes_per_cohort(cohort_id: str) -> None:
    rung = 4 if cohort_id == "concentrated_stress" else 3
    bundle = emit_synthetic_household(cohort_id=cohort_id, seed=11, rung=rung)
    result = run_workflow_smoke(bundle)
    assert result.ok, result.checks


def test_concentrated_stress_policy_monitoring_alerts() -> None:
    bundle = emit_synthetic_household(
        cohort_id="concentrated_stress", seed=99, rung=4
    )
    result = run_workflow_smoke(bundle)
    policy = next(
        c for c in result.checks if c.workflow == "policy_monitoring"
    )
    assert policy.ok
    restricted = frozenset(bundle.ips.restricted_securities)
    positions = lot_positions_from_fixture(
        bundle.fixture, restricted_tickers=restricted
    )
    drift = build_ips_drift_report_from_views(
        bundle.fixture.household_id, positions, bundle.ips
    )
    assert drift.alerts or drift.concentration_alerts


def test_concentrated_stress_optimizer_documents_binding() -> None:
    bundle = emit_synthetic_household(
        cohort_id="concentrated_stress", seed=99, rung=4
    )
    result = run_workflow_smoke(bundle)
    rebalance = next(
        c for c in result.checks if c.workflow == "rebalance_tax_overlay"
    )
    assert rebalance.ok
    assert "binding_constraints=" in rebalance.detail


def test_concentrated_stress_qp_documents_binding() -> None:
    """po0: the constrained-MV QP binds a sleeve bound on the stress book."""
    from warehouse.decision.optimizer.rebalance import run_mv_rebalance

    bundle = emit_synthetic_household(
        cohort_id="concentrated_stress", seed=42, rung=4, validate=False
    )
    positions = lot_positions_from_fixture(bundle.fixture)
    proposal = run_mv_rebalance(positions, bundle.ips)
    # Concentrated single-name → w* clips against IPS sleeve bounds.
    assert proposal.binding_bounds
    # Σw = 1 re-asserted (AssetPortfolio validator is not in this path).
    total = sum(proposal.target_weights.values())
    assert abs(total - 1) < 0.0001  # type: ignore[operator]


def test_scenario_card_fingerprint_stable() -> None:
    first = build_scenario_card(rung_level=3, seed=3)
    second = build_scenario_card(rung_level=3, seed=3)
    assert first.risk_fingerprint == second.risk_fingerprint
    assert first.ips_id is not None
    assert first.ips_id == second.ips_id


def test_scenario_card_includes_ips_metadata() -> None:
    card = build_scenario_card(
        rung_level=4, seed=99, cohort_id="concentrated_stress"
    )
    assert card.ips_id is not None
    assert card.ips_id.startswith("ips_")
    assert card.binding_constraints_count >= 1
