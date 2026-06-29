"""Falsifiers for the per-plane testing registry (st1)."""

from __future__ import annotations

import pytest

from warehouse.config import repo_root
from warehouse.dashboard.status import PLANES
from warehouse.dashboard.testing_data import (
    PlaneTestResult,
    measure_pyramid_mix,
)
from warehouse.dashboard.testing_registry import (
    PLANE_TEST_SLICES,
    QA_FOOTNOTE_PLANE_IDS,
    collect_pytest_paths,
    operational_plane_ids,
    registry_plane_ids,
    slice_by_plane_id,
    status_plane_id,
)

_ROOT = repo_root()
_FLOOR_MIN = 50.0
_FLOOR_MAX = 100.0
_CRITICAL_PLANE_IDS = frozenset({"data", "decision"})


def test_every_status_plane_has_registry_slice() -> None:
    for plane in PLANES:
        plane_id = status_plane_id(plane)
        row = slice_by_plane_id(plane_id)
        assert row is not None, f"missing registry slice for {plane.name}"
        assert row.package == plane.package
        assert row.name == plane.name


def test_registry_includes_infra_and_cross_cutting() -> None:
    ids = set(registry_plane_ids())
    assert set(operational_plane_ids()) <= ids
    assert "infra" in ids
    assert "cross_cutting" in ids
    assert len(PLANE_TEST_SLICES) == len(ids)


def test_qa_footnote_planes_cover_operational() -> None:
    footnote_ids = frozenset(QA_FOOTNOTE_PLANE_IDS)
    operational = frozenset(operational_plane_ids())
    assert operational <= footnote_ids
    assert "infra" in footnote_ids


_SLICE_IDS = [row.plane_id for row in PLANE_TEST_SLICES]


@pytest.mark.parametrize("slice_row", PLANE_TEST_SLICES, ids=_SLICE_IDS)
def test_pytest_paths_exist(slice_row) -> None:
    for rel_path in collect_pytest_paths(slice_row):
        path = _ROOT / rel_path
        assert path.is_file(), f"{slice_row.plane_id}: missing {rel_path}"


@pytest.mark.parametrize("slice_row", PLANE_TEST_SLICES, ids=_SLICE_IDS)
def test_collect_pytest_paths_includes_property_paths(slice_row) -> None:
    merged = collect_pytest_paths(slice_row)
    for rel_path in slice_row.property_paths:
        if rel_path in slice_row.pytest_paths:
            assert rel_path in merged
        elif (_ROOT / rel_path).is_file():
            assert rel_path in merged


_SHIPPED_PROPERTY_PATHS = (
    "tests/test_lot_properties.py",
    "tests/test_optimizer_properties.py",
    "tests/test_risk_properties.py",
)

_SHIPPED_STATISTICAL_PATHS = (
    "tests/test_synth_distribution.py",
    "tests/test_synth_null_baseline.py",
    "tests/test_synth_sdg_ablation.py",
    "tests/test_synth_cross_regime.py",
)


@pytest.mark.parametrize("rel_path", _SHIPPED_PROPERTY_PATHS)
def test_shipped_property_paths_exist(rel_path: str) -> None:
    path = _ROOT / rel_path
    assert path.is_file(), f"missing shipped property suite {rel_path}"


@pytest.mark.parametrize("rel_path", _SHIPPED_STATISTICAL_PATHS)
def test_shipped_statistical_paths_exist(rel_path: str) -> None:
    path = _ROOT / rel_path
    assert path.is_file(), f"missing shipped statistical suite {rel_path}"


@pytest.mark.parametrize("slice_row", PLANE_TEST_SLICES, ids=_SLICE_IDS)
def test_coverage_floors_sane(slice_row) -> None:
    assert _FLOOR_MIN <= slice_row.coverage_floor_pct <= _FLOOR_MAX


@pytest.mark.parametrize("slice_row", PLANE_TEST_SLICES, ids=_SLICE_IDS)
def test_coverage_glob_non_empty(slice_row) -> None:
    assert slice_row.coverage_glob.strip()


@pytest.mark.parametrize(
    "slice_row",
    [row for row in PLANE_TEST_SLICES if row.report_mutation],
    ids=lambda s: s.plane_id,
)
def test_mutation_targets_exist(slice_row) -> None:
    assert slice_row.mutation_targets, (
        f"{slice_row.plane_id}: report_mutation requires mutation_targets"
    )
    for rel_path in slice_row.mutation_targets:
        path = _ROOT / rel_path
        assert path.is_file(), f"{slice_row.plane_id}: missing {rel_path}"


@pytest.mark.parametrize(
    "slice_row",
    [row for row in PLANE_TEST_SLICES if row.plane_id in _CRITICAL_PLANE_IDS],
    ids=lambda s: s.plane_id,
)
def test_critical_planes_register_property_paths(slice_row) -> None:
    assert slice_row.property_paths, (
        f"{slice_row.plane_id}: critical plane needs property_paths"
    )
    for rel_path in slice_row.property_paths:
        assert rel_path.startswith("tests/")
        assert rel_path.endswith(".py")


def test_measure_pyramid_mix_sums_to_one_hundred() -> None:
    mix = measure_pyramid_mix()
    total = mix.unit_pct + mix.integration_pct + mix.e2e_pct
    assert total == pytest.approx(100.0, abs=0.2)
    assert mix.unit_pct >= 0.0
    assert mix.integration_pct >= 0.0
    assert mix.e2e_pct >= 0.0


def test_coverage_below_floor_does_not_gate_ok() -> None:
    plane = PlaneTestResult(
        plane_id="data",
        name="Data",
        tests=23,
        passed=23,
        failed=0,
        coverage_pct=85.7,
        coverage_floor_pct=90.0,
        risk_tier="critical",
    )
    assert plane.ok is True
    assert plane.coverage_status == "below_floor"


def test_overall_ok_requires_all_planes_green() -> None:
    from warehouse.dashboard.testing_data import TestingReport

    report = TestingReport.model_validate(
        {
            "has_report": True,
            "overall": {
                "tests": 10,
                "passed": 10,
                "failed": 0,
                "coverage_pct": 90.0,
                "planes_below_floor": 0,
            },
            "planes": [
                {
                    "plane_id": "data",
                    "name": "Data",
                    "tests": 5,
                    "passed": 5,
                    "failed": 0,
                    "coverage_pct": 95.0,
                    "coverage_floor_pct": 90.0,
                    "coverage_status": "ok",
                    "risk_tier": "critical",
                },
                {
                    "plane_id": "execution",
                    "name": "Execution",
                    "tests": 5,
                    "passed": 4,
                    "failed": 1,
                    "coverage_pct": 95.0,
                    "coverage_floor_pct": 90.0,
                    "coverage_status": "ok",
                    "risk_tier": "high",
                },
            ],
        }
    )
    assert report.planes[0].ok is True
    assert report.planes[1].ok is False
    assert report.overall.ok is False


def test_testing_report_json_round_trip() -> None:
    from warehouse.dashboard.testing_data import TestingReport

    report = TestingReport.model_validate(
        {
            "generated_at": "2026-06-29T12:00:00Z",
            "git_sha": "abc123",
            "stale": False,
            "has_report": True,
            "pyramid": {
                "unit_pct": 70.0,
                "integration_pct": 25.0,
                "e2e_pct": 5.0,
            },
            "overall": {
                "tests": 1,
                "passed": 1,
                "failed": 0,
                "coverage_pct": 89.2,
                "planes_below_floor": 0,
            },
            "planes": [
                {
                    "plane_id": "infra",
                    "name": "Infrastructure",
                    "tests": 1,
                    "passed": 1,
                    "failed": 0,
                    "coverage_pct": 86.6,
                    "coverage_floor_pct": 85.0,
                    "coverage_status": "ok",
                    "risk_tier": "medium",
                    "pytest_paths": ["tests/test_config.py"],
                }
            ],
        }
    )
    payload = report.model_dump(mode="json")
    restored = TestingReport.model_validate(payload)
    assert restored.overall.ok is True
    assert restored.planes[0].coverage_status == "ok"
