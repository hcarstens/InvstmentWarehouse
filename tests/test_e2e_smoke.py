"""Falsifiers for E2E smoke artifact + dashboard wiring (st4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from warehouse.dashboard.e2e_data import (
    build_e2e_panel_from_matrix,
    e2e_smoke_artifact_path,
    empty_e2e_panel,
    generate_e2e_smoke_artifact,
    load_e2e_smoke_dashboard,
    write_e2e_smoke_artifact,
)
from warehouse.dashboard.render_e2e import render_e2e_smoke_section
from warehouse.dashboard.render_testing import render_testing_matrix
from warehouse.dashboard.testing_data import (
    E2eSmokeSummary,
    load_testing_report,
)
from warehouse.dashboard.testing_data import (
    TestingReport as TestingReportModel,
)
from warehouse.dashboard.testing_report import (
    attach_e2e_smoke_to_report,
    generate_testing_report,
)
from warehouse.research.synthetic.workflow_smoke import (
    E2eMatrixResult,
    WorkflowSmokeCheck,
    WorkflowSmokeResult,
    run_e2e_matrix,
)


def _fake_matrix() -> E2eMatrixResult:
    rows = [
        WorkflowSmokeResult(
            cohort_id=cohort,
            seed=42,
            rung=3 if cohort != "concentrated_stress" else 4,
            checks=[
                WorkflowSmokeCheck(
                    workflow="policy_monitoring",
                    ok=True,
                    detail="ok",
                )
            ],
        )
        for cohort in (
            "general_hnw",
            "uhnw_inherited",
            "founder_executive",
            "concentrated_stress",
        )
    ]
    return E2eMatrixResult(results=rows)


def test_e2e_smoke_summary_ok_when_all_pass() -> None:
    summary = E2eSmokeSummary(households=4, passed=4)
    assert summary.ok is True


def test_e2e_smoke_summary_not_ok_when_partial() -> None:
    summary = E2eSmokeSummary(households=4, passed=3)
    assert summary.ok is False


def test_generate_e2e_smoke_artifact_writes_json(tmp_path: Path) -> None:
    path = tmp_path / "e2e_smoke.json"
    panel = generate_e2e_smoke_artifact(
        artifact_path=path,
        matrix_runner=_fake_matrix,
    )
    assert path.is_file()
    assert panel.households == 4
    assert panel.passed == 4
    assert panel.all_ok is True
    loaded = load_e2e_smoke_dashboard(artifact_path=path)
    assert loaded.has_artifact is True
    assert loaded.passed == 4


def test_load_e2e_dashboard_empty_without_artifact(tmp_path: Path) -> None:
    data = load_e2e_smoke_dashboard(artifact_path=tmp_path / "missing.json")
    assert data.panel_status == "empty"
    assert data.households == 0


def test_research_panel_reads_artifact_not_live_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "e2e_smoke.json"
    generate_e2e_smoke_artifact(
        artifact_path=path,
        matrix_runner=_fake_matrix,
    )

    def boom() -> E2eMatrixResult:
        raise AssertionError("live run_e2e_matrix must not run on page load")

    monkeypatch.setattr(
        "warehouse.dashboard.e2e_data.run_e2e_matrix",
        boom,
    )
    data = load_e2e_smoke_dashboard(artifact_path=path)
    assert data.all_ok is True
    html = render_e2e_smoke_section(data)
    assert "artifact-backed" in html
    assert "4/4" in html or "4 households pass" in html


def test_render_e2e_empty_state_mentions_test_report() -> None:
    html = render_e2e_smoke_section(empty_e2e_panel())
    assert "warehouse test report" in html
    assert "no artifact" in html


def test_testing_headline_shows_e2e_4_of_4(tmp_path: Path) -> None:
    artifact = tmp_path / "last_report.json"
    report = TestingReportModel.model_validate(
        {
            "has_report": True,
            "e2e_smoke": {"households": 4, "passed": 4, "ok": True},
            "overall": {
                "tests": 10,
                "passed": 10,
                "failed": 0,
                "coverage_pct": 90.0,
                "planes_below_floor": 0,
            },
            "planes": [
                {
                    "plane_id": "research",
                    "name": "Research",
                    "tests": 5,
                    "passed": 5,
                    "failed": 0,
                    "coverage_pct": 95.0,
                    "coverage_floor_pct": 93.0,
                    "coverage_status": "ok",
                    "risk_tier": "high",
                }
            ],
        }
    )
    write_path = artifact
    write_path.write_text(
        json.dumps(report.model_dump(mode="json")),
        encoding="utf-8",
    )
    loaded = load_testing_report(artifact_path=artifact)
    panel = render_testing_matrix(loaded)
    assert "4/4" in panel
    assert "E2E smoke" in panel


def test_e2e_smoke_gates_overall_ok() -> None:
    report = TestingReportModel.model_validate(
        {
            "has_report": True,
            "e2e_smoke": {"households": 4, "passed": 3, "ok": False},
            "overall": {
                "tests": 10,
                "passed": 10,
                "failed": 0,
            },
            "planes": [
                {
                    "plane_id": "research",
                    "name": "Research",
                    "tests": 5,
                    "passed": 5,
                    "failed": 0,
                    "coverage_floor_pct": 93.0,
                    "risk_tier": "high",
                }
            ],
        }
    )
    assert report.overall.ok is False


def test_attach_e2e_smoke_to_report_embeds_summary(tmp_path: Path) -> None:
    e2e_path = tmp_path / "e2e_smoke.json"
    base = TestingReportModel.model_validate(
        {
            "has_report": True,
            "overall": {"tests": 1, "passed": 1, "failed": 0},
            "planes": [],
        }
    )
    updated = attach_e2e_smoke_to_report(
        base,
        e2e_artifact_path=e2e_path,
        matrix_runner=_fake_matrix,
    )
    assert updated.e2e_smoke is not None
    assert updated.e2e_smoke.households == 4
    assert updated.e2e_smoke.passed == 4
    assert e2e_path.is_file()


def test_generate_testing_report_writes_e2e_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "last_report.json"
    cov_path = tmp_path / "coverage.json"
    e2e_path = tmp_path / "e2e_smoke.json"
    cov_path.write_text(json.dumps({"files": {}}), encoding="utf-8")

    def fake_build(**kwargs: object) -> tuple[TestingReportModel, int]:
        _ = kwargs
        report = TestingReportModel.model_validate(
            {
                "has_report": True,
                "overall": {"tests": 3, "passed": 3, "failed": 0},
                "planes": [],
            }
        )
        return report, 0

    monkeypatch.setattr(
        "warehouse.dashboard.testing_report.build_testing_report",
        fake_build,
    )
    exit_code = generate_testing_report(
        artifact_path=artifact,
        coverage_path=cov_path,
        matrix_runner=_fake_matrix,
    )
    assert exit_code == 0
    loaded = load_testing_report(artifact_path=artifact)
    assert loaded.e2e_smoke is not None
    assert loaded.e2e_smoke.passed == 4
    assert e2e_path.is_file()


def test_build_e2e_panel_from_matrix_collects_leg_names() -> None:
    panel = build_e2e_panel_from_matrix(_fake_matrix())
    assert "policy_monitoring" in panel.leg_names
    assert panel.to_summary().households == 4


def test_e2e_matrix_all_cohorts_green() -> None:
    """Falsifier: full live matrix passes every leg (PR gate)."""
    matrix = run_e2e_matrix()
    assert matrix.summary["households"] == 4
    assert matrix.ok, [
        (r.cohort_id, c.workflow, c.detail)
        for r in matrix.results
        for c in r.checks
        if not c.ok
    ]


def test_e2e_matrix_deterministic() -> None:
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


def test_write_e2e_smoke_artifact_round_trips(tmp_path: Path) -> None:
    panel = build_e2e_panel_from_matrix(_fake_matrix())
    path = tmp_path / "e2e.json"
    write_e2e_smoke_artifact(panel, artifact_path=path)
    loaded = load_e2e_smoke_dashboard(artifact_path=path)
    assert loaded.households == panel.households


def test_default_e2e_artifact_path_under_runs_testing() -> None:
    path = e2e_smoke_artifact_path()
    assert path.name == "e2e_smoke.json"
    assert path.parent.name == "testing"
