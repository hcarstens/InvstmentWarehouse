"""Per-plane pytest mapping — single source of truth for the testing matrix."""

from __future__ import annotations

from pydantic import BaseModel, Field

from warehouse.config import repo_root
from warehouse.dashboard.status import PLANES, PlaneStatus

# Pyramid targets (ST4) — actual mix measured, not assumed.
PYRAMID_TARGET = {"unit_pct": 70.0, "integration_pct": 25.0, "e2e_pct": 5.0}

# Classify collected tests by path when markers are absent (plan §3).
_E2E_EXACT_PATHS = frozenset(
    {
        "tests/test_dashboard.py",
        "tests/test_risk_build_dashboard.py",
    }
)
_INTEGRATION_EXACT_PATHS = frozenset(
    {
        "tests/test_orchestrator.py",
        "tests/test_risk_integration.py",
    }
)
_INTEGRATION_PATH_MARKERS = (
    "test_phase",
    "test_messaging_",
    "workflow",
    "_integration",
)

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
    mutation_targets: list[str] = Field(default_factory=list)
    property_paths: list[str] = Field(default_factory=list)
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
            "tests/test_lot_properties.py",
        ],
        coverage_glob="src/warehouse/data/**",
        coverage_floor_pct=90.0,
        risk_tier="critical",
        report_mutation=True,
        mutation_targets=["src/warehouse/data/ledger/__init__.py"],
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
            "tests/test_synth_distribution.py",
            "tests/test_synth_null_baseline.py",
            "tests/test_synth_sdg_ablation.py",
            "tests/test_synth_cross_regime.py",
            "tests/test_risk_asset_test_suite.py",
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
            "tests/test_optimizer_properties.py",
            "tests/test_pm_narrative.py",
            "tests/test_pm_workflow.py",
            "tests/test_analyst_attribution.py",
            "tests/test_analyst_depth.py",
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
        note=(
            "ReconBreakType taxonomy shipped (qa1); "
            "OMS cancel/replace boundaries shipped (qa2)"
        ),
    ),
    PlaneTestSlice(
        plane_id="reporting",
        name="Reporting",
        package="warehouse.reporting",
        pytest_paths=[
            "tests/test_phase4.py",
            "tests/test_reporting_performance.py",
            "tests/test_reporting_tax.py",
            "tests/test_report_writer.py",
        ],
        coverage_glob="src/warehouse/reporting/**",
        coverage_floor_pct=80.0,
        risk_tier="medium",
        note="Performance + tax scenarios; after_tax_return_ytd shipped (qa7)",
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
            "tests/test_architecture.py",
            "tests/test_dashboard.py",
            "tests/test_risk_build_dashboard.py",
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


def collect_pytest_paths(slice_row: PlaneTestSlice) -> list[str]:
    """Merge pytest_paths and shipped property_paths (deduped, st5a)."""
    root = repo_root()
    seen: set[str] = set()
    merged: list[str] = []
    for rel_path in slice_row.pytest_paths:
        if rel_path not in seen:
            seen.add(rel_path)
            merged.append(rel_path)
    for rel_path in slice_row.property_paths:
        if rel_path in seen:
            continue
        if (root / rel_path).is_file():
            seen.add(rel_path)
            merged.append(rel_path)
    return merged


def slice_by_plane_id(plane_id: str) -> PlaneTestSlice | None:
    for row in PLANE_TEST_SLICES:
        if row.plane_id == plane_id:
            return row
    return None


def status_plane_id(plane: PlaneStatus) -> str:
    """Map ``status.PLANES`` row to registry ``plane_id``."""
    return plane.package.rsplit(".", 1)[-1]


def operational_plane_ids() -> tuple[str, ...]:
    """Five operational planes from ``status.PLANES`` (excludes infra)."""
    return tuple(status_plane_id(plane) for plane in PLANES)


def registry_plane_ids() -> tuple[str, ...]:
    return tuple(row.plane_id for row in PLANE_TEST_SLICES)


def classify_pyramid_layer(rel_path: str) -> str:
    """Return unit | integration | e2e for a collected test path."""
    path = rel_path.replace("\\", "/")
    if path.startswith("tests/integration/"):
        return "e2e"
    if path in _E2E_EXACT_PATHS or "smoke" in path:
        return "e2e"
    if path in _INTEGRATION_EXACT_PATHS:
        return "integration"
    if any(marker in path for marker in _INTEGRATION_PATH_MARKERS):
        return "integration"
    return "unit"
