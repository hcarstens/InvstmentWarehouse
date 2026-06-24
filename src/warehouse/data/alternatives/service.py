"""Alternatives sub-ledger — manual marks, capital calls, distributions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.infra.audit.store import write_audit
from warehouse.infra.db.models import AlternativeEventRow, AlternativeHoldingRow


class AlternativeHoldingView(BaseModel):
    holding_id: str
    household_id: str
    entity_id: str
    name: str
    asset_type: str
    committed_capital: Decimal
    called_capital: Decimal
    current_nav: Decimal
    last_mark_date: date


class AlternativeEventView(BaseModel):
    event_id: str
    holding_id: str
    event_type: str
    amount: Decimal
    event_date: date
    notes: str


def list_alternative_holdings(
    session: Session, household_id: str
) -> list[AlternativeHoldingView]:
    rows = session.scalars(
        select(AlternativeHoldingRow)
        .where(AlternativeHoldingRow.household_id == household_id)
        .order_by(AlternativeHoldingRow.name)
    ).all()
    return [_holding_to_view(r) for r in rows]


def list_alternative_events(
    session: Session, household_id: str, limit: int = 20
) -> list[AlternativeEventView]:
    holdings = session.scalars(
        select(AlternativeHoldingRow.holding_id).where(
            AlternativeHoldingRow.household_id == household_id
        )
    ).all()
    if not holdings:
        return []
    rows = session.scalars(
        select(AlternativeEventRow)
        .where(AlternativeEventRow.holding_id.in_(holdings))
        .order_by(AlternativeEventRow.event_date.desc())
        .limit(limit)
    ).all()
    return [_event_to_view(r) for r in rows]


def record_alternative_event(
    session: Session,
    holding_id: str,
    *,
    event_type: str,
    amount: Decimal,
    event_date: date,
    notes: str = "",
    actor_id: str = "advisor:demo",
) -> AlternativeEventView:
    holding = session.get(AlternativeHoldingRow, holding_id)
    if holding is None:
        raise ValueError(f"Alternative holding not found: {holding_id}")

    event_id = f"alt_evt_{uuid4().hex[:12]}"
    session.add(
        AlternativeEventRow(
            event_id=event_id,
            holding_id=holding_id,
            event_type=event_type,
            amount=amount,
            event_date=event_date,
            notes=notes,
        )
    )

    if event_type == "mark":
        holding.current_nav = amount
        holding.last_mark_date = event_date
    elif event_type == "capital_call":
        holding.called_capital += amount
    elif event_type == "distribution":
        holding.current_nav = max(holding.current_nav - amount, Decimal("0"))

    write_audit(
        session,
        actor_id=actor_id,
        action=f"alt_{event_type}",
        resource_type="alternative_holding",
        resource_id=holding_id,
        household_id=holding.household_id,
        details={"amount": str(amount), "event_id": event_id},
    )
    return _event_to_view(
        AlternativeEventRow(
            event_id=event_id,
            holding_id=holding_id,
            event_type=event_type,
            amount=amount,
            event_date=event_date,
            notes=notes,
        )
    )


def _holding_to_view(row: AlternativeHoldingRow) -> AlternativeHoldingView:
    return AlternativeHoldingView(
        holding_id=row.holding_id,
        household_id=row.household_id,
        entity_id=row.entity_id,
        name=row.name,
        asset_type=row.asset_type,
        committed_capital=row.committed_capital,
        called_capital=row.called_capital,
        current_nav=row.current_nav,
        last_mark_date=row.last_mark_date,
    )


def _event_to_view(row: AlternativeEventRow) -> AlternativeEventView:
    return AlternativeEventView(
        event_id=row.event_id,
        holding_id=row.holding_id,
        event_type=row.event_type,
        amount=row.amount,
        event_date=row.event_date,
        notes=row.notes,
    )
