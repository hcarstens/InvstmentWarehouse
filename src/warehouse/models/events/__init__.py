"""Immutable transaction event stream."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class EventType(StrEnum):
    TRADE = "trade"
    TRANSFER = "transfer"
    DIVIDEND = "dividend"
    CAPITAL_CALL = "capital_call"
    DISTRIBUTION = "distribution"
    MARK = "mark"
    CORPORATE_ACTION = "corporate_action"


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    account_id: str
    event_type: EventType
    occurred_at: datetime
    security_id: str | None = None
    quantity: Decimal | None = None
    amount: Decimal | None = None
    metadata: dict[str, str] = {}
