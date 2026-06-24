"""Persist and query audit log entries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.infra.audit import AuditEntry
from warehouse.infra.db.models import AuditLogRow


def write_audit(
    session: Session,
    *,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    household_id: str | None = None,
    details: dict[str, str] | None = None,
) -> AuditEntry:
    entry = AuditEntry(
        entry_id=f"audit_{uuid4().hex[:12]}",
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        household_id=household_id,
        occurred_at=datetime.now(UTC),
        details=details or {},
    )
    session.add(
        AuditLogRow(
            entry_id=entry.entry_id,
            actor_id=entry.actor_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            household_id=entry.household_id,
            occurred_at=entry.occurred_at,
            details=json.dumps(entry.details),
        )
    )
    return entry


def list_audit_entries(
    session: Session,
    *,
    household_id: str | None = None,
    limit: int = 50,
) -> list[AuditEntry]:
    stmt = select(AuditLogRow).order_by(AuditLogRow.occurred_at.desc()).limit(limit)
    if household_id:
        stmt = stmt.where(AuditLogRow.household_id == household_id)
    rows = session.scalars(stmt).all()
    return [
        AuditEntry(
            entry_id=row.entry_id,
            actor_id=row.actor_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            household_id=row.household_id,
            occurred_at=row.occurred_at,
            details=json.loads(row.details),
        )
        for row in rows
    ]
