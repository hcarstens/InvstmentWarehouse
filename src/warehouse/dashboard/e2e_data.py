"""End-to-end smoke matrix panel data — live, in-process, no DB.

Generates a household per cohort (portfolio + IPS via the synthetic
generators) and drives the **whole stack** on each — policy drift, v0 TLH,
optimizer v1 (po0/po1/po2 MV-QP + scenario-robust stress), scenario card, and
the ``pm.advise`` coordinator — reporting per-leg pass/fail (§ workflow_smoke).

This is the living proof that portfolio + IPS generation feed every plane: the
panel shows real system state across the cohort matrix. Failures surface in the
``error`` field or as ``ok=False`` rows rather than disappearing (CLAUDE.md).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse.research.synthetic import run_e2e_matrix


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
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rows: list[E2eMatrixRowData] = Field(default_factory=list)
    households: int = 0
    passed: int = 0
    leg_names: list[str] = Field(default_factory=list)
    panel_status: str = "live"
    error: str | None = None

    @property
    def all_ok(self) -> bool:
        return self.households > 0 and self.passed == self.households


def load_e2e_smoke_dashboard() -> E2ePanelData:
    try:
        matrix = run_e2e_matrix()
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
    except Exception as err:
        return E2ePanelData(panel_status="error", error=str(err))
