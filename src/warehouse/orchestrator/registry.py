"""In-flight request register — state transparency at the gate (OM8)."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from warehouse.orchestrator.models import (
    InFlightRecord,
    InFlightStage,
    OrchestratorRequest,
)

_MAX = 100

_RECORDS: deque[InFlightRecord] = deque(maxlen=_MAX)
_STARTED_AT: dict[str, datetime] = {}


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def start(
    request: OrchestratorRequest, *, correlation_id: str
) -> InFlightRecord:
    now = datetime.now(UTC)
    record = InFlightRecord(
        correlation_id=correlation_id,
        intent=request.intent,
        household_id=request.household_id,
        stage=InFlightStage.ROUTING,
        started_at=_iso(now),
    )
    _RECORDS.append(record)
    _STARTED_AT[correlation_id] = now
    return record


def advance(
    correlation_id: str,
    *,
    stage: InFlightStage,
    assigned_actor: str | None = None,
) -> None:
    if not _RECORDS or _RECORDS[-1].correlation_id != correlation_id:
        _patch_latest(
            correlation_id,
            stage=stage,
            assigned_actor=assigned_actor,
        )
        return
    latest = _RECORDS[-1]
    _RECORDS[-1] = latest.model_copy(
        update={
            "stage": stage,
            "assigned_actor": assigned_actor or latest.assigned_actor,
        }
    )


def complete(correlation_id: str) -> None:
    now = datetime.now(UTC)
    started = _STARTED_AT.pop(correlation_id, now)
    elapsed = int((now - started).total_seconds() * 1000)
    _patch_latest(
        correlation_id,
        stage=InFlightStage.COMPLETED,
        finished_at=_iso(now),
        elapsed_ms=elapsed,
    )


def fail(correlation_id: str) -> None:
    now = datetime.now(UTC)
    started = _STARTED_AT.pop(correlation_id, now)
    elapsed = int((now - started).total_seconds() * 1000)
    _patch_latest(
        correlation_id,
        stage=InFlightStage.FAILED,
        finished_at=_iso(now),
        elapsed_ms=elapsed,
    )


def _patch_latest(
    correlation_id: str,
    *,
    stage: InFlightStage | None = None,
    assigned_actor: str | None = None,
    finished_at: str | None = None,
    elapsed_ms: int | None = None,
) -> None:
    for idx in range(len(_RECORDS) - 1, -1, -1):
        if _RECORDS[idx].correlation_id != correlation_id:
            continue
        current = _RECORDS[idx]
        updates: dict[str, object] = {}
        if stage is not None:
            updates["stage"] = stage
        if assigned_actor is not None:
            updates["assigned_actor"] = assigned_actor
        if finished_at is not None:
            updates["finished_at"] = finished_at
        if elapsed_ms is not None:
            updates["elapsed_ms"] = elapsed_ms
        _RECORDS[idx] = current.model_copy(update=updates)
        return


def recent(limit: int = 20) -> list[InFlightRecord]:
    return list(_RECORDS)[-limit:][::-1]


def clear() -> None:
    """Reset register (tests)."""
    _RECORDS.clear()
    _STARTED_AT.clear()
