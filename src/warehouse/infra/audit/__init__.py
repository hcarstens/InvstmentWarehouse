"""Immutable audit log — who changed what, when."""

from datetime import datetime

from pydantic import BaseModel


class AuditEntry(BaseModel):
    entry_id: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    household_id: str | None = None
    occurred_at: datetime
    details: dict[str, str] = {}
