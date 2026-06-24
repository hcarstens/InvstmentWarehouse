"""Custodian ingest runner."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.data.ingest.registry import get_parser
from warehouse.data.ingest.schwab_csv import CustodianPositionRecord
from warehouse.infra.audit.store import write_audit
from warehouse.infra.db.models import CustodianPositionRow, IngestRunRow, SecurityRow


class IngestRunSummary(BaseModel):
    run_id: str
    custodian_id: str
    file_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    rows_processed: int
    error_message: str | None = None


def _ticker_to_security_id(session: Session, ticker: str) -> str:
    row = session.scalar(select(SecurityRow).where(SecurityRow.ticker == ticker))
    if row is None:
        raise ValueError(f"Unknown ticker {ticker!r} — add to security master first")
    return row.security_id


def run_custodian_ingest(
    session: Session,
    path: Path,
    *,
    custodian_id: str = "custodian_schwab",
    actor_id: str = "system:ingest",
    household_id: str | None = None,
) -> IngestRunSummary:
    run_id = f"ingest_{uuid4().hex[:12]}"
    started = datetime.now(UTC)
    run = IngestRunRow(
        run_id=run_id,
        custodian_id=custodian_id,
        file_name=path.name,
        status="running",
        started_at=started,
        rows_processed=0,
    )
    session.add(run)
    session.flush()

    try:
        records = get_parser(custodian_id)(path)
        for record in records:
            security_id = _ticker_to_security_id(session, record.ticker)
            session.add(
                CustodianPositionRow(
                    ingest_run_id=run_id,
                    account_id=record.account_id,
                    security_id=security_id,
                    quantity=record.quantity,
                    as_of_date=record.as_of_date,
                )
            )
        run.status = "success"
        run.rows_processed = len(records)
        run.finished_at = datetime.now(UTC)
        write_audit(
            session,
            actor_id=actor_id,
            action="ingest_complete",
            resource_type="ingest_run",
            resource_id=run_id,
            household_id=household_id,
            details={"file": path.name, "rows": str(len(records))},
        )
    except Exception as err:
        run.status = "error"
        run.error_message = str(err)
        run.finished_at = datetime.now(UTC)
        write_audit(
            session,
            actor_id=actor_id,
            action="ingest_failed",
            resource_type="ingest_run",
            resource_id=run_id,
            household_id=household_id,
            details={"file": path.name, "error": str(err)},
        )
        raise

    return IngestRunSummary(
        run_id=run.run_id,
        custodian_id=run.custodian_id,
        file_name=run.file_name,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        rows_processed=run.rows_processed,
        error_message=run.error_message,
    )


def list_ingest_runs(session: Session, limit: int = 10) -> list[IngestRunSummary]:
    rows = session.scalars(
        select(IngestRunRow).order_by(IngestRunRow.started_at.desc()).limit(limit)
    ).all()
    return [
        IngestRunSummary(
            run_id=row.run_id,
            custodian_id=row.custodian_id,
            file_name=row.file_name,
            status=row.status,
            started_at=row.started_at,
            finished_at=row.finished_at,
            rows_processed=row.rows_processed,
            error_message=row.error_message,
        )
        for row in rows
    ]


def load_custodian_positions(
    session: Session, ingest_run_id: str
) -> list[CustodianPositionRecord]:
    rows = session.scalars(
        select(CustodianPositionRow).where(CustodianPositionRow.ingest_run_id == ingest_run_id)
    ).all()
    result: list[CustodianPositionRecord] = []
    for row in rows:
        ticker = session.scalar(
            select(SecurityRow.ticker).where(SecurityRow.security_id == row.security_id)
        )
        if ticker is None:
            raise ValueError(f"Security {row.security_id} missing from master")
        result.append(
            CustodianPositionRecord(
                account_id=row.account_id,
                ticker=ticker,
                quantity=row.quantity,
                as_of_date=row.as_of_date,
            )
        )
    return result
