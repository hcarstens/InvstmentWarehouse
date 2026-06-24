"""Post-ingest reconciliation — custodian vs lot ledger."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from warehouse.infra.audit.store import write_audit
from warehouse.infra.db.models import (
    CustodianPositionRow,
    EntityRelationshipRow,
    LotRow,
    ReconciliationBreakRow,
    SecurityRow,
)
from warehouse.models.entities import RelationshipType


class ReconciliationBreak(BaseModel):
    break_id: str
    ingest_run_id: str
    account_id: str
    security_id: str | None
    description: str
    opened_at: datetime
    resolved_at: datetime | None
    resolved: bool


def _ledger_quantities(session: Session) -> dict[tuple[str, str], Decimal]:
    rows = session.execute(
        select(LotRow.account_id, LotRow.security_id, func.sum(LotRow.quantity)).group_by(
            LotRow.account_id, LotRow.security_id
        )
    ).all()
    return {(account_id, security_id): quantity for account_id, security_id, quantity in rows}


def _accounts_for_custodian(session: Session, custodian_id: str) -> set[str]:
    rows = session.scalars(
        select(EntityRelationshipRow.source_id).where(
            EntityRelationshipRow.target_id == custodian_id,
            EntityRelationshipRow.relationship_type == RelationshipType.CUSTODIED_AT.value,
        )
    ).all()
    return set(rows)


def reconcile_ingest(
    session: Session,
    ingest_run_id: str,
    *,
    actor_id: str = "system:reconcile",
    household_id: str | None = None,
) -> list[ReconciliationBreak]:
    from warehouse.infra.db.models import IngestRunRow

    ingest_run = session.get(IngestRunRow, ingest_run_id)
    if ingest_run is None:
        raise ValueError(f"Ingest run not found: {ingest_run_id}")
    custodian_accounts = _accounts_for_custodian(session, ingest_run.custodian_id)

    custodian_rows = session.scalars(
        select(CustodianPositionRow).where(CustodianPositionRow.ingest_run_id == ingest_run_id)
    ).all()
    ledger = _ledger_quantities(session)
    breaks: list[ReconciliationBreak] = []
    seen: set[tuple[str, str]] = set()

    for row in custodian_rows:
        key = (row.account_id, row.security_id)
        seen.add(key)
        ledger_qty = ledger.get(key, Decimal("0"))
        if ledger_qty != row.quantity:
            ticker = session.scalar(
                select(SecurityRow.ticker).where(SecurityRow.security_id == row.security_id)
            )
            break_id = f"break_{uuid4().hex[:12]}"
            description = (
                f"{ticker or row.security_id}: custodian={row.quantity}, ledger={ledger_qty}"
            )
            opened = datetime.now(UTC)
            session.add(
                ReconciliationBreakRow(
                    break_id=break_id,
                    ingest_run_id=ingest_run_id,
                    account_id=row.account_id,
                    security_id=row.security_id,
                    description=description,
                    opened_at=opened,
                    resolved=False,
                )
            )
            write_audit(
                session,
                actor_id=actor_id,
                action="recon_break_opened",
                resource_type="reconciliation_break",
                resource_id=break_id,
                household_id=household_id,
                details={"ingest_run_id": ingest_run_id, "description": description},
            )
            breaks.append(
                ReconciliationBreak(
                    break_id=break_id,
                    ingest_run_id=ingest_run_id,
                    account_id=row.account_id,
                    security_id=row.security_id,
                    description=description,
                    opened_at=opened,
                    resolved_at=None,
                    resolved=False,
                )
            )

    for (account_id, security_id), ledger_qty in ledger.items():
        if account_id not in custodian_accounts:
            continue
        if (account_id, security_id) in seen:
            continue
        if ledger_qty == 0:
            continue
        ticker = session.scalar(
            select(SecurityRow.ticker).where(SecurityRow.security_id == security_id)
        )
        break_id = f"break_{uuid4().hex[:12]}"
        description = f"{ticker or security_id}: custodian=0, ledger={ledger_qty}"
        opened = datetime.now(UTC)
        session.add(
            ReconciliationBreakRow(
                break_id=break_id,
                ingest_run_id=ingest_run_id,
                account_id=account_id,
                security_id=security_id,
                description=description,
                opened_at=opened,
                resolved=False,
            )
        )
        breaks.append(
            ReconciliationBreak(
                break_id=break_id,
                ingest_run_id=ingest_run_id,
                account_id=account_id,
                security_id=security_id,
                description=description,
                opened_at=opened,
                resolved_at=None,
                resolved=False,
            )
        )

    return breaks


def list_reconciliation_breaks(
    session: Session,
    *,
    open_only: bool = True,
    limit: int = 50,
) -> list[ReconciliationBreak]:
    stmt = select(ReconciliationBreakRow).order_by(ReconciliationBreakRow.opened_at.desc())
    if open_only:
        stmt = stmt.where(ReconciliationBreakRow.resolved.is_(False))
    rows = session.scalars(stmt.limit(limit)).all()
    return [
        ReconciliationBreak(
            break_id=row.break_id,
            ingest_run_id=row.ingest_run_id,
            account_id=row.account_id,
            security_id=row.security_id,
            description=row.description,
            opened_at=row.opened_at,
            resolved_at=row.resolved_at,
            resolved=row.resolved,
        )
        for row in rows
    ]
