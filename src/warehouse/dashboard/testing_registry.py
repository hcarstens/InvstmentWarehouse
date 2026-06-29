"""Per-plane pytest mapping — single source of truth for the testing matrix."""

from __future__ import annotations

from pydantic import BaseModel

# Pyramid targets (ST4) — actual mix measured in st2 CLI report.
PYRAMID_TARGET = {"unit_pct": 70.0, "integration_pct": 25.0, "e2e_pct": 5.0}

# Plane pages that show a QA footnote (§4.8).
QA_FOOTNOTE_PLANE_IDS: tuple[str, ...] = (
    "data",
    "research",
    "decision",
    "execution",
    "reporting",
    "infra",
)


class PlaneTestSlice(BaseModel):
    plane_id: str
    name: str
    package: str
    pytest_paths: list[str]
    coverage_glob: str
    coverage_floor_pct: float
    risk_tier: str  # critical | high | medium
    report_mutation: bool = False
    mutation_targets: list[str] = []
    property_paths: list[str] = []
    note: str = ""


PLANE_TEST_SLICES: list[PlaneTestSlice] = [
    PlaneTestSlice(
        plane_id="data",
        name="Data",
        package="warehouse.data",
        pytest_paths=[
            "tests/test_phase1.py",
            "tests/test_phase2.py",
            "tests/test_architecture.py",
        ],
        coverage_glob="src/warehouse/data/**",
        coverage_floor_pct=90.0,
        risk_tier="critical",
        report_mutation=True,
        mutation_targets=["src/warehouse/data/lot_ledger.py"],
        property_paths=["tests/test_lot_properties.py"],
    ),
    PlaneTestSlice(
        plane_id="research",
        name="Research",
        package="warehouse.research",
        pytest_paths=[
            "tests/test_risk_api.py",
            "tests/test_risk_dashboard.py",
            "tests/test_risk_hnw_combinations.py",
            "tests/test_risk_integration.py",
            "tests/test_risk_observability.py",
            "tests/test_risk_scenarios.py",
            "tests/test_risk_service.py",
            "tests/test_risk_synthetic.py",
            "tests/test_risk_v1.py",
            "tests/test_hnw_synthetic.py",
            "tests/test_synthetic_ips.py",
            "tests/test_synthetic_ips_integration.py",
            "tests/test_synthetic_ips_workflow.py",
            "tests/test_ips_policy_fields.py",
            "tests/test_ips_sleeves.py",
            "tests/integration/test_end_to_end_synthetic.py",
        ],
        coverage_glob="src/warehouse/research/**",
        coverage_floor_pct=93.0,
        risk_tier="high",
        property_paths=["tests/test_risk_properties.py"],
    ),
    PlaneTestSlice(
        plane_id="decision",
        name="Decision",
        package="warehouse.decision",
        pytest_paths=[
            "tests/test_phase3.py",
            "tests/test_optimizer_mapping.py",
            "tests/test_optimizer_qp.py",
            "tests/test_optimizer_rebalance.py",
            "tests/test_optimizer_robust.py",
            "tests/test_optimizer_tax_seam.py",
            "tests/test_optimizer_turnover.py",
            "tests/test_pm_narrative.py",
            "tests/test_pm_workflow.py",
            "tests/test_analyst_attribution.py",
            "tests/test_analyst_npa.py",
            "tests/test_analyst_review.py",
            "tests/test_analyst_thesis.py",
            "tests/test_orchestrator.py",
        ],
        coverage_glob="src/warehouse/decision/**",
        coverage_floor_pct=93.0,
        risk_tier="critical",
        report_mutation=True,
        mutation_targets=["src/warehouse/decision/optimizer/qp.py"],
        property_paths=["tests/test_optimizer_properties.py"],
    ),
    PlaneTestSlice(
        plane_id="execution",
        name="Execution",
        package="warehouse.execution",
        pytest_paths=[
            "tests/test_phase2.py",
            "tests/test_phase4.py",
        ],
        coverage_glob="src/warehouse/execution/**",
        coverage_floor_pct=90.0,
        risk_tier="high",
    ),
    PlaneTestSlice(
        plane_id="reporting",
        name="Reporting",
        package="warehouse.reporting",
        pytest_paths=["tests/test_phase4.py"],
        coverage_glob="src/warehouse/reporting/**",
        coverage_floor_pct=80.0,
        risk_tier="medium",
        note="Interim pass via decision tax until reporting ships",
    ),
    PlaneTestSlice(
        plane_id="infra",
        name="Infrastructure",
        package="warehouse.infra",
        pytest_paths=[
            "tests/test_infra_health.py",
            "tests/test_config.py",
            "tests/test_frozen.py",
        ],
        coverage_glob="src/warehouse/infra/**",
        coverage_floor_pct=85.0,
        risk_tier="medium",
    ),
    PlaneTestSlice(
        plane_id="cross_cutting",
        name="Cross-cutting",
        package="warehouse",
        pytest_paths=[
            "tests/test_messaging_coordinator.py",
            "tests/test_messaging_core.py",
            "tests/test_messaging_events.py",
            "tests/test_messaging_handlers.py",
            "tests/test_dashboard.py",
            "tests/integration/test_end_to_end_synthetic.py",
        ],
        coverage_glob=(
            "src/warehouse/workflows/**,"
            "src/warehouse/messaging/**,"
            "src/warehouse/orchestrator/**,"
            "src/warehouse/models/**,"
            "src/warehouse/dashboard/**,"
            "src/warehouse/config.py,"
            "src/warehouse/integrity/**"
        ),
        coverage_floor_pct=80.0,
        risk_tier="medium",
    ),
]


def slice_by_plane_id(plane_id: str) -> PlaneTestSlice | None:
    for row in PLANE_TEST_SLICES:
        if row.plane_id == plane_id:
            return row
    return None
