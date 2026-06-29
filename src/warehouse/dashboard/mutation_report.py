"""Mutation kill reporting for critical planes (st5h).

ST3: ``mutation_kill_pct`` supplements line coverage on Data + Decision —
report-only, never gates ``ok`` (¬QA6). ST4: scoped ``mutmut`` on registry
``mutation_targets`` only; on-demand via ``warehouse test mutation`` (minutes,
not seconds — not on PR path).

Kill verdict comes from pytest failures on mutated code (ST2), not mutmut
self-report alone — each plane run uses ``collect_pytest_paths`` for the
test oracle.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from warehouse.config import repo_root
from warehouse.dashboard.testing_data import PlaneTestResult, current_git_sha
from warehouse.dashboard.testing_registry import (
    PLANE_TEST_SLICES,
    PlaneTestSlice,
    collect_pytest_paths,
)

_MUTMUT_SECTION_RE = re.compile(r"\n\[tool\.mutmut\][^\[]*", re.DOTALL)
_MUTANTS_DIR = Path("mutants")
_CICD_STATS_REL = _MUTANTS_DIR / "mutmut-cicd-stats.json"

RunMutmut = Callable[..., subprocess.CompletedProcess[str]]
RunPytest = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class MutationPlaneResult:
    plane_id: str
    target_path: str
    total_mutants: int
    killed: int
    survived: int
    skipped: int
    kill_pct: float


def mutation_artifact_path() -> Path:
    return repo_root() / "runs" / "testing" / "mutation_report.json"


def compute_kill_pct(killed: int, survived: int) -> float:
    """Return kill % from killed/survived counts (one decimal, ST5)."""
    evaluated = killed + survived
    if evaluated == 0:
        return 0.0
    return round(100.0 * killed / evaluated, 1)


def counts_from_cicd_stats(
    payload: dict[str, Any],
) -> tuple[int, int, int, int]:
    """Parse mutmut ``mutmut-cicd-stats.json`` counts (ST2 oracle)."""
    killed = int(payload.get("killed", 0))
    survived = int(payload.get("survived", 0))
    skipped = int(payload.get("skipped", 0))
    total = int(payload.get("total", killed + survived + skipped))
    return killed, survived, skipped, total


def parse_mutmut_status_line(text: str) -> tuple[int, int, int] | None:
    """Parse mutmut progress line: killed, survived, skipped."""
    for line in reversed(text.splitlines()):
        if "🎉" not in line or "🙁" not in line:
            continue
        killed_m = re.search(r"🎉\s*(\d+)", line)
        survived_m = re.search(r"🙁\s*(\d+)", line)
        skipped_m = re.search(r"🔇\s*(\d+)", line)
        if killed_m and survived_m:
            killed = int(killed_m.group(1))
            survived = int(survived_m.group(1))
            skipped = int(skipped_m.group(1)) if skipped_m else 0
            return killed, survived, skipped
    return None


def mutmut_config_section(slice_row: PlaneTestSlice) -> str:
    """Build ``[tool.mutmut]`` TOML block for a single registry plane."""
    if not slice_row.mutation_targets:
        raise ValueError(
            f"plane {slice_row.plane_id} has report_mutation but no targets"
        )
    target = slice_row.mutation_targets[0]
    test_paths = collect_pytest_paths(slice_row)
    lines = [
        "[tool.mutmut]",
        f'source_paths = ["{target}"]',
        f'only_mutate = ["{target}"]',
        'pytest_add_cli_args = ["-q", "--tb=no", "--disable-warnings"]',
        "pytest_add_cli_args_test_selection = [",
    ]
    for rel_path in test_paths:
        lines.append(f'    "{rel_path}",')
    lines.append("]")
    return "\n".join(lines) + "\n"


def patch_pyproject_mutmut(content: str, section: str) -> str:
    """Replace or append ``[tool.mutmut]`` in ``pyproject.toml``."""
    stripped = _MUTMUT_SECTION_RE.sub("", content).rstrip()
    return f"{stripped}\n\n{section}"


@contextmanager
def _plane_mutmut_config(
    slice_row: PlaneTestSlice,
    *,
    project_root: Path,
) -> Iterator[None]:
    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file():
        raise RuntimeError(f"missing pyproject.toml at {pyproject}")
    original = pyproject.read_text(encoding="utf-8")
    section = mutmut_config_section(slice_row)
    pyproject.write_text(
        patch_pyproject_mutmut(original, section),
        encoding="utf-8",
    )
    try:
        from mutmut.configuration import Config

        Config.reset()
        yield
    finally:
        pyproject.write_text(original, encoding="utf-8")
        from mutmut.configuration import Config

        Config.reset()


def _default_mutmut_runner(
    args: list[str],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [sys.executable, "-m", "mutmut", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=7200,
        )
    except (OSError, subprocess.SubprocessError) as err:
        raise RuntimeError(f"mutmut invocation failed: {args!r}") from err


def _clear_mutants_dir(cwd: Path) -> None:
    mutants = cwd / _MUTANTS_DIR
    if mutants.is_dir():
        shutil.rmtree(mutants)


def _read_cicd_stats(cwd: Path) -> dict[str, Any]:
    path = cwd / _CICD_STATS_REL
    if not path.is_file():
        raise RuntimeError(
            f"mutmut did not write CI/CD stats at {path}; "
            "run mutmut export-cicd-stats after mutmut run"
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise RuntimeError(f"failed to read mutmut stats at {path}") from err
    if not isinstance(raw, dict):
        raise RuntimeError(f"mutmut stats at {path} is not a JSON object")
    return raw


def run_plane_mutation(
    slice_row: PlaneTestSlice,
    *,
    cwd: Path,
    runner: RunMutmut | None = None,
    run_pytest: RunPytest | None = None,
) -> MutationPlaneResult:
    """Run scoped mutmut for one plane; baseline pytest must be green first."""
    from warehouse.dashboard.testing_report import (
        _default_run_pytest,
        run_plane_pytest,
    )

    pytest_runner = run_pytest or _default_run_pytest
    passed, failed, _total = run_plane_pytest(
        slice_row,
        cwd=cwd,
        run_pytest=pytest_runner,
    )
    if failed > 0:
        raise RuntimeError(
            f"plane {slice_row.plane_id} pytest not green before mutation: "
            f"{passed} passed, {failed} failed"
        )

    target = slice_row.mutation_targets[0]
    mutmut_runner = runner or _default_mutmut_runner

    with _plane_mutmut_config(slice_row, project_root=cwd):
        _clear_mutants_dir(cwd)
        run_proc = mutmut_runner(["run"], cwd=cwd)
        if run_proc.returncode not in {0, 1, 2}:
            detail = run_proc.stderr.strip() or run_proc.stdout.strip()
            raise RuntimeError(
                f"mutmut run for {slice_row.plane_id} target {target} "
                f"exited {run_proc.returncode}: {detail}"
            )

        export_proc = mutmut_runner(["export-cicd-stats"], cwd=cwd)
        if export_proc.returncode != 0:
            detail = export_proc.stderr.strip() or export_proc.stdout.strip()
            raise RuntimeError(
                f"mutmut export-cicd-stats for {slice_row.plane_id} "
                f"exited {export_proc.returncode}: {detail}"
            )

    stats = _read_cicd_stats(cwd)
    killed, survived, skipped, total = counts_from_cicd_stats(stats)
    return MutationPlaneResult(
        plane_id=slice_row.plane_id,
        target_path=target,
        total_mutants=total,
        killed=killed,
        survived=survived,
        skipped=skipped,
        kill_pct=compute_kill_pct(killed, survived),
    )


def load_mutation_artifact(path: Path | None = None) -> dict[str, float]:
    """Return plane_id → kill_pct from artifact, or empty when absent."""
    artifact = path or mutation_artifact_path()
    if not artifact.is_file():
        return {}
    try:
        raw = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise RuntimeError(
            f"failed to read mutation artifact at {artifact}"
        ) from err
    planes = raw.get("planes")
    if not isinstance(planes, list):
        raise RuntimeError(
            f"mutation artifact at {artifact} missing 'planes' list"
        )
    kill_by_plane: dict[str, float] = {}
    for entry in planes:
        if not isinstance(entry, dict):
            continue
        plane_id = entry.get("plane_id")
        kill_pct = entry.get("kill_pct")
        if isinstance(plane_id, str) and isinstance(kill_pct, (int, float)):
            kill_by_plane[plane_id] = float(kill_pct)
    return kill_by_plane


def merge_mutation_into_planes(
    planes: list[PlaneTestResult],
    kill_by_plane: dict[str, float],
) -> list[PlaneTestResult]:
    """Populate mutation_kill_pct on planes with report_mutation data."""
    if not kill_by_plane:
        return planes
    merged: list[PlaneTestResult] = []
    for plane in planes:
        kill_pct = kill_by_plane.get(plane.plane_id)
        if kill_pct is None:
            merged.append(plane)
        else:
            merged.append(
                plane.model_copy(update={"mutation_kill_pct": kill_pct})
            )
    return merged


def write_mutation_artifact(
    results: list[MutationPlaneResult],
    *,
    artifact_path: Path | None = None,
) -> Path:
    path = artifact_path or mutation_artifact_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_sha": current_git_sha(),
        "planes": [
            {
                "plane_id": r.plane_id,
                "target_path": r.target_path,
                "total_mutants": r.total_mutants,
                "killed": r.killed,
                "survived": r.survived,
                "skipped": r.skipped,
                "kill_pct": r.kill_pct,
            }
            for r in results
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def generate_mutation_report(
    *,
    cwd: Path | None = None,
    artifact_path: Path | None = None,
    runner: RunMutmut | None = None,
    run_pytest: RunPytest | None = None,
) -> Path:
    """Run mutmut per critical plane and write ``mutation_report.json``."""
    root = cwd or repo_root()
    slices = [row for row in PLANE_TEST_SLICES if row.report_mutation]
    if not slices:
        raise RuntimeError("no planes with report_mutation in registry")

    results: list[MutationPlaneResult] = []
    for slice_row in slices:
        results.append(
            run_plane_mutation(
                slice_row,
                cwd=root,
                runner=runner,
                run_pytest=run_pytest,
            )
        )
    return write_mutation_artifact(results, artifact_path=artifact_path)
