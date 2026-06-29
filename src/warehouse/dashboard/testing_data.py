"""Testing matrix data — artifact loader or empty-state for the dashboard."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from warehouse.config import repo_root
from warehouse.dashboard.testing_registry import (
    PLANE_TEST_SLICES,
    PYRAMID_TARGET,
    PlaneTestSlice,
)

_ARTIFACT_PATH = repo_root() / "runs" / "testing" / "last_report.json"


class PyramidMix(BaseModel):
    unit_pct: float
    integration_pct: float
    e2e_pct: float


class OverallTestSummary(BaseModel):
    tests: int = 0
    passed: int = 0
    failed: int = 0
    coverage_pct: float | None = None
    planes_below_floor: int = 0
    ok: bool = True

    @model_validator(mode="after")
    def _sync_ok(self) -> OverallTestSummary:
        object.__setattr__(self, "ok", self.failed == 0)
        return self


class PlaneTestResult(BaseModel):
    plane_id: str
    name: str
    tests: int = 0
    passed: int = 0
    failed: int = 0
    coverage_pct: float | None = None
    coverage_floor_pct: float
    coverage_status: str = "unknown"  # ok | below_floor | unknown
    mutation_kill_pct: float | None = None
    risk_tier: str
    ok: bool = True
    pytest_paths: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sync_ok(self) -> PlaneTestResult:
        object.__setattr__(self, "ok", self.failed == 0)
        return self


class TestingReport(BaseModel):
    generated_at: datetime | None = None
    git_sha: str | None = None
    stale: bool = False
    has_report: bool = False
    pyramid: PyramidMix | None = None
    overall: OverallTestSummary
    planes: list[PlaneTestResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sync_overall_ok(self) -> TestingReport:
        plane_ok = all(p.ok for p in self.planes)
        overall_ok = self.overall.failed == 0 and plane_ok
        object.__setattr__(
            self,
            "overall",
            self.overall.model_copy(update={"ok": overall_ok}),
        )
        return self


def testing_artifact_path() -> Path:
    return _ARTIFACT_PATH


def _current_git_sha() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root(),
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = proc.stdout.strip()
    return sha or None


def _coverage_status(coverage_pct: float | None, floor_pct: float) -> str:
    if coverage_pct is None:
        return "unknown"
    if coverage_pct >= floor_pct:
        return "ok"
    return "below_floor"


def _empty_plane_row(slice_row: PlaneTestSlice) -> PlaneTestResult:
    return PlaneTestResult(
        plane_id=slice_row.plane_id,
        name=slice_row.name,
        coverage_floor_pct=slice_row.coverage_floor_pct,
        coverage_status="unknown",
        risk_tier=slice_row.risk_tier,
        pytest_paths=list(slice_row.pytest_paths),
    )


def empty_testing_report() -> TestingReport:
    """No artifact — registry rows with unknown metrics (st0 stub state)."""
    return TestingReport(
        has_report=False,
        pyramid=None,
        overall=OverallTestSummary(),
        planes=[_empty_plane_row(row) for row in PLANE_TEST_SLICES],
    )


def _planes_below_floor(planes: list[PlaneTestResult]) -> int:
    return sum(1 for p in planes if p.coverage_status == "below_floor")


def load_testing_report(
    *,
    artifact_path: Path | None = None,
) -> TestingReport:
    """Load ``runs/testing/last_report.json`` or return empty-state."""
    path = artifact_path or _ARTIFACT_PATH
    if not path.is_file():
        return empty_testing_report()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        report = TestingReport.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValueError):
        return empty_testing_report()

    current_sha = _current_git_sha()
    stale = bool(
        report.git_sha and current_sha and report.git_sha != current_sha
    )
    planes_below = _planes_below_floor(report.planes)
    overall = report.overall.model_copy(
        update={"planes_below_floor": planes_below}
    )
    return report.model_copy(
        update={
            "has_report": True,
            "stale": stale,
            "overall": overall,
        }
    )


def pyramid_target_mix() -> PyramidMix:
    return PyramidMix(**PYRAMID_TARGET)
