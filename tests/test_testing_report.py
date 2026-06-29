"""Falsifiers for testing report CLI and aggregation (st2)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from warehouse.cli import main
from warehouse.dashboard.testing_data import (
    TestingReport as TestingReportModel,
)
from warehouse.dashboard.testing_data import (
    load_testing_report,
)
from warehouse.dashboard.testing_registry import PLANE_TEST_SLICES
from warehouse.dashboard.testing_report import (
    bucket_line_coverage_pct,
    build_testing_report,
    coverage_glob_prefixes,
    file_matches_bucket,
    generate_testing_report,
    parse_pytest_summary,
    warehouse_line_coverage_pct,
    write_testing_report,
)


def _sample_coverage_files() -> dict:
    return {
        "src/warehouse/data/ledger/foo.py": {
            "summary": {
                "num_statements": 100,
                "missing_lines": 10,
            },
        },
        "src/warehouse/decision/optimizer/qp.py": {
            "summary": {
                "num_statements": 50,
                "missing_lines": 5,
            },
        },
        "src/warehouse/config.py": {
            "summary": {
                "num_statements": 20,
                "missing_lines": 4,
            },
        },
        "src/warehouse/workflows/daily.py": {
            "summary": {
                "num_statements": 30,
                "missing_lines": 6,
            },
        },
    }


def test_coverage_glob_prefixes_splits_comma_separated() -> None:
    prefixes = coverage_glob_prefixes(
        "src/warehouse/workflows/**,src/warehouse/config.py"
    )
    assert prefixes == ("src/warehouse/workflows/", "src/warehouse/config.py")


def test_bucket_line_coverage_pct_aggregates_matching_files() -> None:
    files = _sample_coverage_files()
    pct = bucket_line_coverage_pct(files, ("src/warehouse/data/",))
    assert pct == pytest.approx(90.0)


def test_warehouse_line_coverage_pct() -> None:
    pct = warehouse_line_coverage_pct(_sample_coverage_files())
    # 200 statements, 25 missing -> 87.5%
    assert pct == pytest.approx(87.5)


def test_parse_pytest_summary_passed_only() -> None:
    assert parse_pytest_summary("...\n3 passed in 0.10s\n") == (3, 0, 3)


def test_parse_pytest_summary_failed_and_passed() -> None:
    text = "FAILED tests/foo.py::test_bar\\n1 failed, 2 passed in 0.12s"
    assert parse_pytest_summary(text) == (2, 1, 3)


def test_coverage_below_floor_does_not_gate_ok_in_built_report(
    tmp_path: Path,
) -> None:
    data_slice = next(r for r in PLANE_TEST_SLICES if r.plane_id == "data")
    files = {
        "src/warehouse/data/ledger/foo.py": {
            "summary": {
                "num_statements": 100,
                "missing_lines": 20,
            },
        },
    }
    cov_path = tmp_path / "coverage.json"
    cov_path.write_text(json.dumps({"files": files}), encoding="utf-8")

    def fake_pytest(
        args: list[str],
        *,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        if "--cov=warehouse" in args:
            return subprocess.CompletedProcess(
                args, 0, "10 passed in 1.0s", ""
            )
        if data_slice.pytest_paths[0] in args:
            return subprocess.CompletedProcess(args, 0, "5 passed in 0.1s", "")
        return subprocess.CompletedProcess(args, 0, "1 passed in 0.1s", "")

    report, exit_code = build_testing_report(
        cwd=tmp_path,
        coverage_path=cov_path,
        run_pytest=fake_pytest,
    )
    data_plane = next(p for p in report.planes if p.plane_id == "data")
    assert exit_code == 0
    assert data_plane.failed == 0
    assert data_plane.ok is True
    assert data_plane.coverage_status == "below_floor"
    assert report.overall.ok is True


def test_overall_ok_requires_all_planes_green(tmp_path: Path) -> None:
    cov_path = tmp_path / "coverage.json"
    cov_path.write_text(json.dumps({"files": {}}), encoding="utf-8")
    decision = next(r for r in PLANE_TEST_SLICES if r.plane_id == "decision")

    def fake_pytest(
        args: list[str],
        *,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        if "--cov=warehouse" in args:
            return subprocess.CompletedProcess(
                args, 0, "10 passed in 1.0s", ""
            )
        if decision.pytest_paths[0] in args:
            return subprocess.CompletedProcess(
                args, 1, "1 failed, 4 passed in 0.1s", ""
            )
        return subprocess.CompletedProcess(args, 0, "2 passed in 0.1s", "")

    report, _ = build_testing_report(
        cwd=tmp_path,
        coverage_path=cov_path,
        run_pytest=fake_pytest,
    )
    decision_plane = next(p for p in report.planes if p.plane_id == "decision")
    assert decision_plane.ok is False
    assert report.overall.ok is False


def test_written_artifact_round_trips_through_loader(tmp_path: Path) -> None:
    artifact = tmp_path / "last_report.json"
    e2e_path = tmp_path / "e2e_smoke.json"
    cov_path = tmp_path / "coverage.json"
    cov_path.write_text(
        json.dumps({"files": _sample_coverage_files()}),
        encoding="utf-8",
    )

    def fake_pytest(
        args: list[str],
        *,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        if "--cov=warehouse" in args:
            return subprocess.CompletedProcess(args, 0, "3 passed in 0.5s", "")
        return subprocess.CompletedProcess(args, 0, "1 passed in 0.1s", "")

    report, _ = build_testing_report(
        cwd=tmp_path,
        coverage_path=cov_path,
        run_pytest=fake_pytest,
    )
    from warehouse.dashboard.testing_report import attach_e2e_smoke_to_report
    from warehouse.research.synthetic.workflow_smoke import (
        E2eMatrixResult,
        WorkflowSmokeCheck,
        WorkflowSmokeResult,
    )

    def _mini_matrix() -> E2eMatrixResult:
        return E2eMatrixResult(
            results=[
                WorkflowSmokeResult(
                    cohort_id="general_hnw",
                    seed=42,
                    rung=3,
                    checks=[
                        WorkflowSmokeCheck(
                            workflow="policy_monitoring",
                            ok=True,
                            detail="ok",
                        )
                    ],
                )
            ]
        )

    report = attach_e2e_smoke_to_report(
        report,
        e2e_artifact_path=e2e_path,
        matrix_runner=_mini_matrix,
    )
    write_testing_report(report, artifact_path=artifact)
    loaded = load_testing_report(artifact_path=artifact)
    assert loaded.has_report is True
    assert loaded.overall.tests == report.overall.tests
    assert len(loaded.planes) == len(report.planes)
    assert loaded.e2e_smoke is not None
    assert loaded.e2e_smoke.households == 1
    restored = TestingReportModel.model_validate(
        json.loads(artifact.read_text(encoding="utf-8"))
    )
    assert restored.overall.ok == loaded.overall.ok
    assert restored.e2e_smoke is not None


def test_generate_testing_report_propagates_pytest_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cov_path = tmp_path / "coverage.json"
    artifact = tmp_path / "last_report.json"

    def fake_build(
        *,
        cwd: Path | None = None,
        artifact_path: Path | None = None,
        coverage_path: Path | None = None,
        run_pytest: object = None,
    ) -> tuple[TestingReportModel, int]:
        _ = cwd, artifact_path, coverage_path, run_pytest
        cov_path.write_text(json.dumps({"files": {}}), encoding="utf-8")
        report = TestingReportModel.model_validate(
            {
                "has_report": True,
                "overall": {
                    "tests": 1,
                    "passed": 0,
                    "failed": 1,
                },
                "planes": [
                    {
                        "plane_id": "infra",
                        "name": "Infrastructure",
                        "tests": 1,
                        "passed": 0,
                        "failed": 1,
                        "coverage_floor_pct": 85.0,
                        "risk_tier": "medium",
                    }
                ],
            }
        )
        return report, 1

    monkeypatch.setattr(
        "warehouse.dashboard.testing_report.build_testing_report",
        fake_build,
    )
    exit_code = generate_testing_report(
        artifact_path=artifact,
        coverage_path=cov_path,
    )
    assert exit_code == 1
    assert artifact.is_file()


def test_cli_report_exits_nonzero_on_pytest_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "warehouse.dashboard.testing_report.generate_testing_report",
        lambda **_: 1,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["test", "report"])
    assert result.exit_code == 1


def test_cli_report_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "last_report.json"

    def fake_generate(**kwargs: object) -> int:
        _ = kwargs
        artifact.write_text("{}", encoding="utf-8")
        return 0

    monkeypatch.setattr(
        "warehouse.dashboard.testing_report.generate_testing_report",
        fake_generate,
    )
    runner = CliRunner()
    result = runner.invoke(main, ["test", "report"])
    assert result.exit_code == 0
    assert "last_report.json" in result.output


def test_file_matches_bucket_exact_file() -> None:
    prefixes = ("src/warehouse/config.py",)
    assert file_matches_bucket("src/warehouse/config.py", prefixes)
    assert not file_matches_bucket("src/warehouse/config_extra.py", prefixes)
