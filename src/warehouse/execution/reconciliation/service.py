"""Post-ingest reconciliation — custodian vs lot ledger."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
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
    MarketPriceRow,
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
        select(
            LotRow.account_id, LotRow.security_id, func.sum(LotRow.quantity)
        ).group_by(LotRow.account_id, LotRow.security_id)
    ).all()
    return {
        (account_id, security_id): quantity
        for account_id, security_id, quantity in rows
    }


def _ledger_as_of_date(session: Session) -> date | None:
    dates = session.scalars(select(MarketPriceRow.as_of_date)).all()
    return max(dates) if dates else None


def _as_of_date_breaks(
    session: Session,
    ingest_run_id: str,
    custodian_rows: Sequence[CustodianPositionRow],
    *,
    actor_id: str,
    household_id: str | None,
) -> list[ReconciliationBreak]:
    """Open breaks when custodian file as_of_date does not match the ledger."""
    if not custodian_rows:
        return []

    breaks: list[ReconciliationBreak] = []
    custodian_dates = {row.as_of_date for row in custodian_rows}
    ledger_as_of = _ledger_as_of_date(session)

    if len(custodian_dates) > 1:
        description = (
            "mixed as_of_date in ingest: "
            f"{sorted(d.isoformat() for d in custodian_dates)}"
        )
        breaks.append(
            _open_break(
                session,
                ingest_run_id=ingest_run_id,
                account_id=custodian_rows[0].account_id,
                security_id=None,
                description=description,
                actor_id=actor_id,
                household_id=household_id,
            )
        )
        return breaks

    custodian_as_of = next(iter(custodian_dates))
    if ledger_as_of is None:
        description = (
            "ledger has no market-price as_of_date; "
            f"custodian={custodian_as_of}"
        )
    elif custodian_as_of != ledger_as_of:
        description = (
            f"stale custodian file: custodian as_of={custodian_as_of}, "
            f"ledger as_of={ledger_as_of}"
        )
    else:
        return breaks

    breaks.append(
        _open_break(
            session,
            ingest_run_id=ingest_run_id,
            account_id=custodian_rows[0].account_id,
            security_id=None,
            description=description,
            actor_id=actor_id,
            household_id=household_id,
        )
    )
    return breaks


def _open_break(
    session: Session,
    *,
    ingest_run_id: str,
    account_id: str,
    security_id: str | None,
    description: str,
    actor_id: str,
    household_id: str | None,
) -> ReconciliationBreak:
    break_id = f"break_{uuid4().hex[:12]}"
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
    write_audit(
        session,
        actor_id=actor_id,
        action="recon_break_opened",
        resource_type="reconciliation_break",
        resource_id=break_id,
        household_id=household_id,
        details={"ingest_run_id": ingest_run_id, "description": description},
    )
    return ReconciliationBreak(
        break_id=break_id,
        ingest_run_id=ingest_run_id,
        account_id=account_id,
        security_id=security_id,
        description=description,
        opened_at=opened,
        resolved_at=None,
        resolved=False,
    )


def _accounts_for_custodian(session: Session, custodian_id: str) -> set[str]:
    rows = session.scalars(
        select(EntityRelationshipRow.source_id).where(
            EntityRelationshipRow.target_id == custodian_id,
            EntityRelationshipRow.relationship_type
            == RelationshipType.CUSTODIED_AT.value,
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
    # autoflush=False — ensure ingest rows from the same txn are visible
    session.flush()
    custodian_accounts = _accounts_for_custodian(
        session, ingest_run.custodian_id
    )

    custodian_rows = session.scalars(
        select(CustodianPositionRow).where(
            CustodianPositionRow.ingest_run_id == ingest_run_id
        )
    ).all()
    ledger = _ledger_quantities(session)
    breaks = _as_of_date_breaks(
        session,
        ingest_run_id,
        custodian_rows,
        actor_id=actor_id,
        household_id=household_id,
    )
    seen: set[tuple[str, str]] = set()

    for row in custodian_rows:
        key = (row.account_id, row.security_id)
        seen.add(key)
        ledger_qty = ledger.get(key, Decimal("0"))
        if ledger_qty != row.quantity:
            ticker = session.scalar(
                select(SecurityRow.ticker).where(
                    SecurityRow.security_id == row.security_id
                )
            )
            sid = ticker or row.security_id
            description = (
                f"{sid}: custodian={row.quantity}, ledger={ledger_qty}"
            )
            breaks.append(
                _open_break(
                    session,
                    ingest_run_id=ingest_run_id,
                    account_id=row.account_id,
                    security_id=row.security_id,
                    description=description,
                    actor_id=actor_id,
                    household_id=household_id,
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
            select(SecurityRow.ticker).where(
                SecurityRow.security_id == security_id
            )
        )
        description = (
            f"{ticker or security_id}: custodian=0, ledger={ledger_qty}"
        )
        breaks.append(
            _open_break(
                session,
                ingest_run_id=ingest_run_id,
                account_id=account_id,
                security_id=security_id,
                description=description,
                actor_id=actor_id,
                household_id=household_id,
            )
        )

    return breaks


def list_reconciliation_breaks(
    session: Session,
    *,
    open_only: bool = True,
    limit: int = 50,
) -> list[ReconciliationBreak]:
    stmt = select(ReconciliationBreakRow).order_by(
        ReconciliationBreakRow.opened_at.desc()
    )
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
