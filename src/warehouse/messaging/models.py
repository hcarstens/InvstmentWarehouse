"""Messaging protocol — envelope, kinds, and dispatch context.

Plane-free types: imports only stdlib, pydantic, sqlalchemy, and
``warehouse.config`` — never a plane. See ``docs/messaging_protocol.md`` §3.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from warehouse.config import Settings

# Module constant now; promotes to an envelope field at Phase 5 (cross-process
# wire versioning) — the adaptability seam (contract §3).
PROTOCOL_VERSION = "0"


class Kind(StrEnum):
    """The request taxonomy — every message is exactly one kind (§2)."""

    QUERY = "query"        # read stored state         — pure, no mutation
    EVALUATE = "evaluate"  # compute over passed input — pure, no mutation
    COMMAND = "command"    # change state              — gated + audited
    EVENT = "event"        # notify of a past change   — fire-and-forget


class Message(BaseModel):
    """Wire envelope — routes, traces, and scopes one request. Immutable."""

    model_config = ConfigDict(frozen=True)

    op: str                          # routes to exactly one handler
    kind: Kind
    payload: BaseModel               # the typed request body (the contract)
    correlation_id: str              # caller-generated — trace one workflow
    household_id: str | None = None  # the scoping key threaded everywhere
    # Self-stamped identity (contract §3):
    message_id: str = Field(default_factory=lambda: uuid4().hex)
    # COMMAND-only seam — reserved; no store in v0:
    idempotency_key: str | None = None


@dataclass(frozen=True)
class DispatchContext:
    """Unit of work for a dispatch — NOT on the wire (no cross-process).

    One ``session`` per orchestrator run = one transaction boundary, threaded
    through nested dispatch unchanged (contract §4.1).
    """

    session: Session
    actor_id: str = "system:messaging"
    settings: Settings | None = None  # resolved by handler/dispatch if None


# --- EVENT payloads (plane-free — primitive fields only, no cycle with the
# plane-typed request bodies in payloads.py) ---


class IngestCompleted(BaseModel):
    household_id: str
    run_id: str
    rows: int


class BreakOpened(BaseModel):
    household_id: str
    break_id: str


class OrderFilled(BaseModel):
    household_id: str
    order_id: str
