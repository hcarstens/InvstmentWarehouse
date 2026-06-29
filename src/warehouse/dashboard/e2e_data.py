"""End-to-end smoke matrix panel data — artifact-backed (st4).

``run_e2e_matrix()`` runs during ``warehouse test report`` and writes
``runs/testing/e2e_smoke.json``. The Research plane panel and ``/testing``
headline read that artifact — they do **not** re-run the full matrix on every
HTTP request (CLAUDE.md errors-bubble; stale badge when git SHA drifts).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from warehouse.config import repo_root
from warehouse.dashboard.testing_data import E2eSmokeSummary, current_git_sha
from warehouse.research.synthetic.workflow_smoke import (
    E2eMatrixResult,
    run_e2e_matrix,
)

_ARTIFACT_PATH = repo_root() / "runs" / "testing" / "e2e_smoke.json"


class E2eLegCell(BaseModel):
    workflow: str
    ok: bool
    detail: str


class E2eMatrixRowData(BaseModel):
    cohort_id: str
    rung: int
    seed: int
    ok: bool
    legs: list[E2eLegCell] = Field(default_factory=list)


class E2ePanelData(BaseModel):
    generated_at: datetime | None = None
    git_sha: str | None = None
    stale: bool = False
    has_artifact: bool = False
    rows: list[E2eMatrixRowData] = Field(default_factory=list)
    households: int = 0
    passed: int = 0
    leg_names: list[str] = Field(default_factory=list)
    panel_status: str = "empty"  # empty | artifact | error
    error: str | None = None

    @property
    def all_ok(self) -> bool:
        return self.households > 0 and self.passed == self.households

    def to_summary(self) -> E2eSmokeSummary:
        return E2eSmokeSummary(households=self.households, passed=self.passed)


def e2e_smoke_artifact_path() -> Path:
    return _ARTIFACT_PATH


def empty_e2e_panel() -> E2ePanelData:
    return E2ePanelData(panel_status="empty")


def build_e2e_panel_from_matrix(matrix: E2eMatrixResult) -> E2ePanelData:
    rows = [
        E2eMatrixRowData(
            cohort_id=result.cohort_id,
            rung=result.rung,
            seed=result.seed,
            ok=result.ok,
            legs=[
                E2eLegCell(workflow=c.workflow, ok=c.ok, detail=c.detail)
                for c in result.checks
            ],
        )
        for result in matrix.results
    ]
    leg_names: list[str] = []
    for row in rows:
        for leg in row.legs:
            if leg.workflow not in leg_names:
                leg_names.append(leg.workflow)
    summary = matrix.summary
    return E2ePanelData(
        rows=rows,
        households=summary["households"],
        passed=summary["passed"],
        leg_names=leg_names,
    )


def write_e2e_smoke_artifact(
    data: E2ePanelData,
    *,
    artifact_path: Path | None = None,
) -> Path:
    path = artifact_path or e2e_smoke_artifact_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _apply_stale(data: E2ePanelData) -> E2ePanelData:
    current_sha = current_git_sha()
    stale = bool(data.git_sha and current_sha and data.git_sha != current_sha)
    return data.model_copy(update={"stale": stale})


def load_e2e_smoke_artifact(
    *,
    artifact_path: Path | None = None,
) -> E2ePanelData:
    """Load persisted E2E smoke JSON or return empty-state."""
    path = artifact_path or e2e_smoke_artifact_path()
    if not path.is_file():
        return empty_e2e_panel()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        data = E2ePanelData.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValueError) as err:
        return E2ePanelData(panel_status="error", error=str(err))

    return _apply_stale(
        data.model_copy(
            update={
                "has_artifact": True,
                "panel_status": "artifact",
            }
        )
    )


def load_e2e_smoke_dashboard(
    *,
    artifact_path: Path | None = None,
) -> E2ePanelData:
    """Dashboard loader — artifact only (no live matrix on page view)."""
    return load_e2e_smoke_artifact(artifact_path=artifact_path)


def generate_e2e_smoke_artifact(
    *,
    artifact_path: Path | None = None,
    matrix_runner: object = run_e2e_matrix,
) -> E2ePanelData:
    """Run the cohort matrix and persist ``e2e_smoke.json``."""
    matrix = matrix_runner()  # type: ignore[operator]
    panel = build_e2e_panel_from_matrix(matrix)
    stamped = panel.model_copy(
        update={
            "generated_at": datetime.now(UTC),
            "git_sha": current_git_sha(),
            "has_artifact": True,
            "panel_status": "artifact",
            "stale": False,
        }
    )
    write_e2e_smoke_artifact(stamped, artifact_path=artifact_path)
    return stamped
