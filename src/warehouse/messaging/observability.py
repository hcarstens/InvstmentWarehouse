"""In-process observability log for emitted events and subscriber failures.

Plane-free and ephemeral (module-level, capped deques). The dashboard reads
this to surface the event stream + isolated subscriber failures
(dashboard-first rule). Phase 5 replaces it with a durable queue.
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from pydantic import BaseModel

_MAX = 100


class EventLogEntry(BaseModel):
    op: str
    correlation_id: str
    household_id: str | None
    occurred_at: datetime


class SubscriberFailureEntry(BaseModel):
    op: str
    error_type: str
    error: str
    occurred_at: datetime


_EVENTS: deque[EventLogEntry] = deque(maxlen=_MAX)
_FAILURES: deque[SubscriberFailureEntry] = deque(maxlen=_MAX)


def record_event(
    op: str, correlation_id: str, household_id: str | None = None
) -> None:
    _EVENTS.append(
        EventLogEntry(
            op=op,
            correlation_id=correlation_id,
            household_id=household_id,
            occurred_at=datetime.now(UTC),
        )
    )


def record_subscriber_failure(op: str, error: Exception) -> None:
    _FAILURES.append(
        SubscriberFailureEntry(
            op=op,
            error_type=type(error).__name__,
            error=str(error),
            occurred_at=datetime.now(UTC),
        )
    )


def recent_events(limit: int = 20) -> list[EventLogEntry]:
    return list(_EVENTS)[-limit:][::-1]


def recent_failures(limit: int = 20) -> list[SubscriberFailureEntry]:
    return list(_FAILURES)[-limit:][::-1]


def clear() -> None:
    """Reset both logs (tests)."""
    _EVENTS.clear()
    _FAILURES.clear()
