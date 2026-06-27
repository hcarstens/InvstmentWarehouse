"""Daily refresh — custodian → reconcile → lots → corp actions → exceptions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.data.ingest.runner import run_custodian_ingest
from warehouse.execution.reconciliation.service import reconcile_ingest
from warehouse.infra.audit.store import write_audit
from warehouse.infra.db.models import DailyRefreshRunRow, DailyRefreshStepRow
from warehouse.research.sandbox import copy_to_research_sandbox

DAILY_REFRESH_STEPS = (
    "custodian_ingest",
    "reconcile",
    "update_lots",
    "corporate_actions",
    "exception_queue",
)


class RefreshStepView(BaseModel):
    step_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    detail: str | None
    error_message: str | None


class DailyRefreshResult(BaseModel):
    run_id: str
    household_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    ingest_run_id: str | None
    steps: list[RefreshStepView]


def _start_step(
    session: Session, refresh_run_id: str, step_name: str
) -> DailyRefreshStepRow:
    step = DailyRefreshStepRow(
        refresh_run_id=refresh_run_id,
        step_name=step_name,
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(step)
    session.flush()
    return step


def _finish_step(
    step: DailyRefreshStepRow,
    *,
    status: str = "success",
    detail: str | None = None,
    error: str | None = None,
) -> None:
    step.status = status
    step.finished_at = datetime.now(UTC)
    step.detail = detail
    step.error_message = error


def run_daily_refresh(
    session: Session,
    custodian_file: Path,
    *,
    household_id: str,
    actor_id: str = "system:daily_refresh",
    use_research_sandbox: bool = True,
) -> DailyRefreshResult:
    run_id = f"refresh_{uuid4().hex[:12]}"
    started = datetime.now(UTC)
    refresh = DailyRefreshRunRow(
        run_id=run_id,
        household_id=household_id,
        status="running",
        started_at=started,
    )
    session.add(refresh)
    session.flush()

    if use_research_sandbox:
        ingest_path = copy_to_research_sandbox(custodian_file)
    else:
        ingest_path = custodian_file
    ingest_run_id: str | None = None
    steps_out: list[RefreshStepView] = []

    try:
        step = _start_step(session, run_id, "custodian_ingest")
        ingest = run_custodian_ingest(
            session,
            ingest_path,
            household_id=household_id,
            actor_id=actor_id,
        )
        ingest_run_id = ingest.run_id
        _finish_step(
            step,
            detail=f"{ingest.rows_processed} rows from {ingest.file_name}",
        )
        steps_out.append(
            RefreshStepView(
                step_name=step.step_name,
                status=step.status,
                started_at=step.started_at,
                finished_at=step.finished_at,
                detail=step.detail,
                error_message=step.error_message,
            )
        )

        step = _start_step(session, run_id, "reconcile")
        breaks = reconcile_ingest(
            session,
            ingest_run_id,
            household_id=household_id,
            actor_id=actor_id,
        )
        _finish_step(step, detail=f"{len(breaks)} break(s)")
        steps_out.append(
            RefreshStepView(
                step_name=step.step_name,
                status=step.status,
                started_at=step.started_at,
                finished_at=step.finished_at,
                detail=step.detail,
                error_message=step.error_message,
            )
        )

        step = _start_step(session, run_id, "update_lots")
        _finish_step(step, detail="Lot ledger unchanged (positions-first v0)")
        steps_out.append(
            RefreshStepView(
                step_name=step.step_name,
                status=step.status,
                started_at=step.started_at,
                finished_at=step.finished_at,
                detail=step.detail,
                error_message=step.error_message,
            )
        )

        step = _start_step(session, run_id, "corporate_actions")
        _finish_step(step, detail="No corporate actions applied")
        steps_out.append(
            RefreshStepView(
                step_name=step.step_name,
                status=step.status,
                started_at=step.started_at,
                finished_at=step.finished_at,
                detail=step.detail,
                error_message=step.error_message,
            )
        )

        step = _start_step(session, run_id, "exception_queue")
        open_breaks = len(breaks)
        _finish_step(step, detail=f"{open_breaks} open break(s) in queue")
        steps_out.append(
            RefreshStepView(
                step_name=step.step_name,
                status=step.status,
                started_at=step.started_at,
                finished_at=step.finished_at,
                detail=step.detail,
                error_message=step.error_message,
            )
        )

        refresh.status = (
            "success" if open_breaks == 0 else "completed_with_breaks"
        )
        refresh.finished_at = datetime.now(UTC)
        write_audit(
            session,
            actor_id=actor_id,
            action="daily_refresh_complete",
            resource_type="daily_refresh_run",
            resource_id=run_id,
            household_id=household_id,
            details={
                "ingest_run_id": ingest_run_id or "",
                "breaks": str(open_breaks),
            },
        )
    except Exception as err:
        refresh.status = "error"
        refresh.finished_at = datetime.now(UTC)
        write_audit(
            session,
            actor_id=actor_id,
            action="daily_refresh_failed",
            resource_type="daily_refresh_run",
            resource_id=run_id,
            household_id=household_id,
            details={"error": str(err)},
        )
        raise

    return DailyRefreshResult(
        run_id=refresh.run_id,
        household_id=refresh.household_id,
        status=refresh.status,
        started_at=refresh.started_at,
        finished_at=refresh.finished_at,
        ingest_run_id=ingest_run_id,
        steps=steps_out,
    )


def latest_refresh_steps(
    session: Session, household_id: str
) -> list[RefreshStepView]:
    run = session.scalar(
        select(DailyRefreshRunRow)
        .where(DailyRefreshRunRow.household_id == household_id)
        .order_by(DailyRefreshRunRow.started_at.desc())
        .limit(1)
    )
    if run is None:
        return []
    rows = session.scalars(
        select(DailyRefreshStepRow)
        .where(DailyRefreshStepRow.refresh_run_id == run.run_id)
        .order_by(DailyRefreshStepRow.id)
    ).all()
    return [
        RefreshStepView(
            step_name=row.step_name,
            status=row.status,
            started_at=row.started_at,
            finished_at=row.finished_at,
            detail=row.detail,
            error_message=row.error_message,
        )
        for row in rows
    ]
