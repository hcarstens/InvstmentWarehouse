"""Falsifiers for mutation kill reporting (st5h).

ST3: kill % is the discriminating signal on Data + Decision — never gates ok.
ST2: parser oracles use independent count math, not merge-code round-trips.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from warehouse.dashboard.mutation_report import (
    MutationPlaneResult,
    compute_kill_pct,
    counts_from_cicd_stats,
    load_mutation_artifact,
    merge_mutation_into_planes,
    mutmut_config_section,
    parse_mutmut_status_line,
    run_plane_mutation,
    write_mutation_artifact,
)
from warehouse.dashboard.testing_data import PlaneTestResult
from warehouse.dashboard.testing_registry import PLANE_TEST_SLICES


def test_kill_pct_from_counts() -> None:
    assert compute_kill_pct(78, 22) == pytest.approx(78.0)
    assert 100.0 * 78 / (78 + 22) == pytest.approx(78.0)


def test_kill_pct_zero_mutants() -> None:
    assert compute_kill_pct(0, 0) == 0.0


def test_counts_from_cicd_stats() -> None:
    killed, survived, skipped, total = counts_from_cicd_stats(
        {
            "killed": 78,
            "survived": 22,
            "skipped": 3,
            "total": 103,
        }
    )
    assert killed == 78
    assert survived == 22
    assert skipped == 3
    assert total == 103
    assert compute_kill_pct(killed, survived) == pytest.approx(78.0)


def test_parse_mutmut_status_line() -> None:
    line = "50/50  🎉 78 🫥 0  ⏰ 0  🤔 0  🙁 22  🔇 3  🧙 0"
    parsed = parse_mutmut_status_line(line)
    assert parsed == (78, 22, 3)


def test_merge_populates_critical_planes_only() -> None:
    planes = [
        PlaneTestResult(
            plane_id="data",
            name="Data",
            coverage_floor_pct=90.0,
            risk_tier="critical",
        ),
        PlaneTestResult(
            plane_id="decision",
            name="Decision",
            coverage_floor_pct=93.0,
            risk_tier="critical",
        ),
        PlaneTestResult(
            plane_id="research",
            name="Research",
            coverage_floor_pct=93.0,
            risk_tier="high",
        ),
    ]
    merged = merge_mutation_into_planes(
        planes,
        {"data": 78.0, "decision": 65.0},
    )
    data = next(p for p in merged if p.plane_id == "data")
    decision = next(p for p in merged if p.plane_id == "decision")
    research = next(p for p in merged if p.plane_id == "research")
    assert data.mutation_kill_pct == pytest.approx(78.0)
    assert decision.mutation_kill_pct == pytest.approx(65.0)
    assert research.mutation_kill_pct is None
    assert data.ok is True
    assert research.ok is True


def test_merge_absent_artifact_leaves_none() -> None:
    planes = [
        PlaneTestResult(
            plane_id="data",
            name="Data",
            coverage_floor_pct=90.0,
            risk_tier="critical",
        ),
    ]
    merged = merge_mutation_into_planes(planes, {})
    assert merged[0].mutation_kill_pct is None


def test_load_mutation_artifact_missing_returns_empty(tmp_path: Path) -> None:
    assert load_mutation_artifact(tmp_path / "missing.json") == {}


def test_load_mutation_artifact_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "mutation_report.json"
    write_mutation_artifact(
        [
            MutationPlaneResult(
                plane_id="data",
                target_path="src/warehouse/data/ledger/__init__.py",
                total_mutants=100,
                killed=78,
                survived=22,
                skipped=0,
                kill_pct=78.0,
            ),
        ],
        artifact_path=path,
    )
    assert load_mutation_artifact(path) == {"data": 78.0}


def test_mutmut_config_includes_registry_paths() -> None:
    data = next(r for r in PLANE_TEST_SLICES if r.plane_id == "data")
    decision = next(r for r in PLANE_TEST_SLICES if r.plane_id == "decision")
    data_section = mutmut_config_section(data)
    decision_section = mutmut_config_section(decision)
    assert "tests/test_lot_properties.py" in data_section
    assert "src/warehouse/data/ledger/__init__.py" in data_section
    assert "tests/test_optimizer_properties.py" in decision_section
    assert "src/warehouse/decision/optimizer/qp.py" in decision_section


def test_run_plane_mutation_uses_injected_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = next(r for r in PLANE_TEST_SLICES if r.plane_id == "data")
    calls: list[list[str]] = []
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")
    monkeypatch.setattr(
        "warehouse.dashboard.mutation_report.repo_root",
        lambda: tmp_path,
    )

    def fake_pytest(
        args: list[str],
        *,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, "5 passed in 0.1s", "")

    def fake_mutmut(
        args: list[str],
        *,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args == ["run"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args == ["export-cicd-stats"]:
            mutants = cwd / "mutants"
            mutants.mkdir(parents=True, exist_ok=True)
            stats = {
                "killed": 8,
                "survived": 2,
                "skipped": 0,
                "total": 10,
            }
            (mutants / "mutmut-cicd-stats.json").write_text(
                json.dumps(stats),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 1, "", "unexpected")

    result = run_plane_mutation(
        data,
        cwd=tmp_path,
        runner=fake_mutmut,
        run_pytest=fake_pytest,
    )
    assert calls == [["run"], ["export-cicd-stats"]]
    assert result.plane_id == "data"
    assert result.kill_pct == pytest.approx(80.0)
    assert result.killed == 8
    assert result.survived == 2
