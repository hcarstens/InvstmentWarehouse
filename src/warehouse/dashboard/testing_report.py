"""Build and write testing report artifacts (st2 CLI backend).

Per-plane pass/fail uses one ``pytest <registry paths> -q`` subprocess per
``PLANE_TEST_SLICES`` row. That is slower than classifying node ids from a
single full-suite collection, but it yields accurate per-plane counts when
registry paths overlap (e.g. ``test_phase2.py`` on Data and Execution).
The full suite runs once with ``--cov`` for overall counts and coverage JSON.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from warehouse.config import repo_root
from warehouse.dashboard.e2e_data import (
    e2e_smoke_artifact_path,
    generate_e2e_smoke_artifact,
)
from warehouse.dashboard.testing_data import (
    OverallTestSummary,
    PlaneTestResult,
    TestingReport,
    _coverage_status,
    _planes_below_floor,
    current_git_sha,
    measure_pyramid_mix,
    testing_artifact_path,
)
from warehouse.dashboard.testing_registry import (
    PLANE_TEST_SLICES,
    PlaneTestSlice,
)

_COVERAGE_PATH = repo_root() / "runs" / "testing" / "coverage.json"
_WAREHOUSE_PREFIX = "src/warehouse/"
RunPytest = Callable[..., subprocess.CompletedProcess[str]]
_SUMMARY_TOKENS = (
    " passed",
    " failed",
    " error",
    " errors",
    " no tests ran",
)


def testing_coverage_path() -> Path:
    return _COVERAGE_PATH


def testing_output_dir() -> Path:
    return repo_root() / "runs" / "testing"


def coverage_glob_prefixes(coverage_glob: str) -> tuple[str, ...]:
    prefixes: list[str] = []
    for raw in coverage_glob.split(","):
        part = raw.strip().replace("\\", "/")
        if not part:
            continue
        if part.endswith("/**"):
            prefixes.append(part[:-3].rstrip("/") + "/")
        elif part.endswith("**"):
            prefixes.append(part[:-2])
        else:
            prefixes.append(part)
    return tuple(prefixes)


def file_matches_bucket(file_path: str, prefixes: tuple[str, ...]) -> bool:
    path = file_path.replace("\\", "/")
    return any(
        path == prefix or path.startswith(prefix.rstrip("/") + "/")
        for prefix in prefixes
    )


def bucket_line_coverage_pct(
    files: dict[str, Any],
    prefixes: tuple[str, ...],
) -> float | None:
    statements = 0
    missing = 0
    for file_path, payload in files.items():
        if not file_matches_bucket(file_path, prefixes):
            continue
        summary = payload.get("summary", {})
        statements += int(summary.get("num_statements", 0))
        missing += int(summary.get("missing_lines", 0))
    if statements == 0:
        return None
    covered = statements - missing
    return 100.0 * covered / statements


def warehouse_line_coverage_pct(files: dict[str, Any]) -> float | None:
    return bucket_line_coverage_pct(files, (_WAREHOUSE_PREFIX,))


def parse_pytest_summary(
    stdout: str,
    stderr: str = "",
) -> tuple[int, int, int]:
    """Return (passed, failed, total) from pytest ``-q`` output."""
    text = "\n".join((stdout, stderr))
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        if not any(token in stripped for token in _SUMMARY_TOKENS):
            continue
        if "no tests ran" in stripped:
            return 0, 0, 0

        failed = 0
        errors = 0
        passed = 0
        match = re.search(r"(\d+) failed", stripped)
        if match:
            failed = int(match.group(1))
        match = re.search(r"(\d+) errors?", stripped)
        if match:
            errors = int(match.group(1))
        match = re.search(r"(\d+) passed", stripped)
        if match:
            passed = int(match.group(1))
        if passed or failed or errors:
            total = passed + failed + errors
            return passed, failed + errors, total
    return 0, 0, 0


def _default_run_pytest(
    args: list[str],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [sys.executable, "-m", "pytest", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=3600,
        )
    except (OSError, subprocess.SubprocessError) as err:
        raise RuntimeError(f"pytest invocation failed: {args!r}") from err


def run_plane_pytest(
    slice_row: PlaneTestSlice,
    *,
    cwd: Path,
    run_pytest: RunPytest = _default_run_pytest,
) -> tuple[int, int, int]:
    proc = run_pytest(
        [*slice_row.pytest_paths, "-q", "--tb=no", "--disable-warnings"],
        cwd=cwd,
    )
    if proc.returncode not in {0, 1, 5}:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(
            f"pytest for plane {slice_row.plane_id} exited "
            f"{proc.returncode}: {detail}"
        )
    if proc.returncode == 5:
        return 0, 0, 0
    return parse_pytest_summary(proc.stdout, proc.stderr)


def load_coverage_files(coverage_path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(coverage_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise RuntimeError(
            f"failed to read coverage JSON at {coverage_path}"
        ) from err
    files = raw.get("files")
    if not isinstance(files, dict):
        raise RuntimeError(
            f"coverage JSON at {coverage_path} missing 'files' mapping"
        )
    return files


def _plane_result(
    slice_row: PlaneTestSlice,
    *,
    passed: int,
    failed: int,
    total: int,
    coverage_pct: float | None,
) -> PlaneTestResult:
    return PlaneTestResult(
        plane_id=slice_row.plane_id,
        name=slice_row.name,
        tests=total,
        passed=passed,
        failed=failed,
        coverage_pct=coverage_pct,
        coverage_floor_pct=slice_row.coverage_floor_pct,
        coverage_status=_coverage_status(
            coverage_pct, slice_row.coverage_floor_pct
        ),
        mutation_kill_pct=None,
        risk_tier=slice_row.risk_tier,
        pytest_paths=list(slice_row.pytest_paths),
    )


def build_testing_report(
    *,
    cwd: Path | None = None,
    artifact_path: Path | None = None,
    coverage_path: Path | None = None,
    run_pytest: RunPytest = _default_run_pytest,
) -> tuple[TestingReport, int]:
    """Run pytest with coverage; return report and full-suite exit code."""
    root = cwd or repo_root()
    cov_path = coverage_path or testing_coverage_path()
    cov_path.parent.mkdir(parents=True, exist_ok=True)
    art_path = artifact_path or testing_artifact_path()
    # Dashboard empty-state tests assume no artifact during the pytest pass.
    if artifact_path is None and art_path.is_file():
        art_path.unlink()

    full_proc = run_pytest(
        [
            "--cov=warehouse",
            f"--cov-report=json:{cov_path}",
            "-q",
            "--tb=no",
            "--disable-warnings",
        ],
        cwd=root,
    )
    if not cov_path.is_file():
        detail = full_proc.stderr.strip() or full_proc.stdout.strip()
        raise RuntimeError(
            f"pytest did not write coverage JSON at {cov_path}: {detail}"
        )

    coverage_files = load_coverage_files(cov_path)
    overall_passed, overall_failed, overall_total = parse_pytest_summary(
        full_proc.stdout, full_proc.stderr
    )

    planes: list[PlaneTestResult] = []
    for slice_row in PLANE_TEST_SLICES:
        passed, failed, total = run_plane_pytest(
            slice_row, cwd=root, run_pytest=run_pytest
        )
        prefixes = coverage_glob_prefixes(slice_row.coverage_glob)
        coverage_pct = bucket_line_coverage_pct(coverage_files, prefixes)
        planes.append(
            _plane_result(
                slice_row,
                passed=passed,
                failed=failed,
                total=total,
                coverage_pct=coverage_pct,
            )
        )

    measure_pyramid_mix.cache_clear()
    pyramid = measure_pyramid_mix()
    overall_coverage = warehouse_line_coverage_pct(coverage_files)
    planes_below = _planes_below_floor(planes)
    overall = OverallTestSummary(
        tests=overall_total,
        passed=overall_passed,
        failed=overall_failed,
        coverage_pct=overall_coverage,
        planes_below_floor=planes_below,
    )
    report = TestingReport(
        generated_at=datetime.now(UTC),
        git_sha=current_git_sha(),
        stale=False,
        has_report=True,
        pyramid=pyramid,
        overall=overall,
        planes=planes,
    )
    _ = artifact_path  # reserved for callers writing to a custom path
    return report, full_proc.returncode


def attach_e2e_smoke_to_report(
    report: TestingReport,
    *,
    e2e_artifact_path: Path | None = None,
    matrix_runner: object = None,
) -> TestingReport:
    """Run E2E matrix, write artifact, embed summary on the report."""
    from warehouse.research.synthetic.workflow_smoke import run_e2e_matrix

    runner = matrix_runner or run_e2e_matrix
    panel = generate_e2e_smoke_artifact(
        artifact_path=e2e_artifact_path or e2e_smoke_artifact_path(),
        matrix_runner=runner,
    )
    return report.model_copy(update={"e2e_smoke": panel.to_summary()})


def write_testing_report(
    report: TestingReport,
    *,
    artifact_path: Path | None = None,
) -> Path:
    path = artifact_path or testing_artifact_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def generate_testing_report(
    *,
    artifact_path: Path | None = None,
    coverage_path: Path | None = None,
    run_pytest: RunPytest = _default_run_pytest,
    matrix_runner: object = None,
) -> int:
    """Build artifacts and return the full-suite pytest exit code."""
    report, exit_code = build_testing_report(
        artifact_path=artifact_path,
        coverage_path=coverage_path,
        run_pytest=run_pytest,
    )
    e2e_path = (
        artifact_path.parent / "e2e_smoke.json"
        if artifact_path is not None
        else e2e_smoke_artifact_path()
    )
    report = attach_e2e_smoke_to_report(
        report,
        e2e_artifact_path=e2e_path,
        matrix_runner=matrix_runner,
    )
    write_testing_report(report, artifact_path=artifact_path)
    return exit_code
