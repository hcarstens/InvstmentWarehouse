"""Synthetic IPS DB seed + dashboard matrix — si4 integration."""

from __future__ import annotations

from warehouse.dashboard.render_phase3 import render_phase3_sections
from warehouse.dashboard.synthetic_ips_data import load_synthetic_ips_matrix
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.ips.monitor import build_ips_drift_report
from warehouse.decision.ips.store import load_ips
from warehouse.infra.db.base import get_session_factory, session_scope
from warehouse.infra.db.synthetic_seed import seed_synthetic_household
from warehouse.research.synthetic import emit_synthetic_household


def test_load_synthetic_ips_matrix_all_cohorts_bind_or_pass() -> None:
    data = load_synthetic_ips_matrix()
    assert data.error is None, data.error
    assert len(data.rows) == 4
    stress = next(r for r in data.rows if r.cohort_id == "concentrated_stress")
    assert stress.binding_count >= 1
    assert stress.validation_ok
    assert stress.smoke_ok


def test_seed_synthetic_household_idempotent() -> None:
    bundle = emit_synthetic_household(
        cohort_id="general_hnw",
        seed=7,
        rung=3,
        household_id="hh_syn_integration_7",
    )
    session = get_session_factory()()
    try:
        created = seed_synthetic_household(session, bundle)
        assert created is True
        again = seed_synthetic_household(session, bundle)
        assert again is False
        ips = load_ips(session, bundle.fixture.household_id)
        assert ips is not None
        assert ips.ips_id == bundle.ips.ips_id
        positions = list_lot_positions(
            session, household_id=bundle.fixture.household_id
        )
        assert len(positions) >= 2
        drift = build_ips_drift_report(
            session,
            bundle.fixture.household_id,
            positions,
            ips,
        )
        assert drift.rows
    finally:
        session.rollback()
        session.close()

    with session_scope() as session:
        assert load_ips(session, bundle.fixture.household_id) is None


def test_render_phase3_includes_synthetic_ips_matrix() -> None:
    from warehouse.dashboard.phase3_data import Phase3DashboardData

    matrix = load_synthetic_ips_matrix()
    html = render_phase3_sections(
        Phase3DashboardData(
            household_id="hh_smith",
            ips_drift=None,
            optimization_runs=[],
            approval_requests=[],
            backtest_runs=[],
            active_constraints=[],
            synthetic_ips=matrix,
        )
    )
    assert "Synthetic IPS binding matrix" in html
    assert "concentrated_stress" in html
