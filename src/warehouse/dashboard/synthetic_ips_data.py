"""Synthetic IPS binding matrix — live cohort × constraint status."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse.research.synthetic import (
    COHORT_IDS,
    emit_synthetic_household,
    run_workflow_smoke,
)

_MATRIX_SEED = 42


def _rung_for_cohort(cohort_id: str) -> int:
    return 4 if cohort_id == "concentrated_stress" else 3


class SyntheticIpsMatrixRow(BaseModel):
    cohort_id: str
    seed: int
    rung: int
    ips_id: str
    binding_count: int
    binding_constraints: list[str] = Field(default_factory=list)
    validation_ok: bool
    smoke_ok: bool
    smoke_detail: str = ""


class SyntheticIpsDashboardData(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    matrix_seed: int = _MATRIX_SEED
    rows: list[SyntheticIpsMatrixRow] = Field(default_factory=list)
    error: str | None = None


def load_synthetic_ips_matrix(
    *,
    matrix_seed: int = _MATRIX_SEED,
) -> SyntheticIpsDashboardData:
    """Emit + smoke each cohort; surface binding counts for the dashboard."""
    try:
        rows: list[SyntheticIpsMatrixRow] = []
        for cohort_id in COHORT_IDS:
            rung = _rung_for_cohort(cohort_id)
            bundle = emit_synthetic_household(
                cohort_id=cohort_id,
                seed=matrix_seed,
                rung=rung,
            )
            smoke = run_workflow_smoke(bundle)
            failed = [c for c in smoke.checks if not c.ok]
            smoke_detail = "; ".join(
                f"{c.workflow}: {c.detail}" for c in smoke.checks
            )
            rows.append(
                SyntheticIpsMatrixRow(
                    cohort_id=cohort_id,
                    seed=matrix_seed,
                    rung=rung,
                    ips_id=bundle.ips.ips_id,
                    binding_count=len(bundle.validation.binding_constraints),
                    binding_constraints=list(
                        bundle.validation.binding_constraints
                    ),
                    validation_ok=bundle.validation.ok,
                    smoke_ok=smoke.ok,
                    smoke_detail=smoke_detail,
                )
            )
            if failed:
                names = ", ".join(c.workflow for c in failed)
                raise RuntimeError(
                    f"workflow smoke failed for {cohort_id}: {names}"
                )
        return SyntheticIpsDashboardData(matrix_seed=matrix_seed, rows=rows)
    except Exception as err:
        return SyntheticIpsDashboardData(
            matrix_seed=matrix_seed,
            error=str(err),
        )
