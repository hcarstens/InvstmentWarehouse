"""Messaging dispatch — registry, request-reply, fire-and-forget events.

PLANE-FREE: must not import any plane (data/decision/execution/research/
reporting). Plane wrappers register from ``warehouse.messaging.handlers``
(the composition root). See ``docs/messaging_protocol.md`` §4.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog
from pydantic import BaseModel

from warehouse.messaging import observability
from warehouse.messaging.models import DispatchContext, Kind, Message

logger = structlog.get_logger(__name__)

# Payload typed ``Any`` so concrete-payload wrappers register cleanly; the
# runtime isinstance check in dispatch enforces the declared payload type.
Handler = Callable[[DispatchContext, Any], BaseModel]
Subscriber = Callable[[DispatchContext, Any], None]

# op -> (payload_type, handler, kind). One handler per op (S2); typed at the
# boundary (S5).
REGISTRY: dict[str, tuple[type[BaseModel], Handler, Kind]] = {}
SUBSCRIBERS: dict[str, list[Subscriber]] = {}


def register(
    op: str,
    payload_type: type[BaseModel],
    handler: Handler,
    kind: Kind,
) -> None:
    """Register the single handler for ``op``; re-registration errors (S2)."""
    if op in REGISTRY:
        raise ValueError(f"op already registered: {op}")
    REGISTRY[op] = (payload_type, handler, kind)


def subscribe(op: str, subscriber: Subscriber) -> None:
    """Add an EVENT subscriber for ``op`` (synchronous fan-out)."""
    SUBSCRIBERS.setdefault(op, []).append(subscriber)


def dispatch_message(ctx: DispatchContext, msg: Message) -> BaseModel:
    """Route ``msg`` to its handler and return the typed result, or raise.

    No error envelope — the exception *is* the error protocol (S7). Context is
    attached via ``add_note`` and re-raised; failures never swallowed.
    """
    if msg.op not in REGISTRY:
        raise KeyError(f"unknown op: {msg.op}")
    payload_type, handler, _kind = REGISTRY[msg.op]
    if not isinstance(msg.payload, payload_type):
        raise TypeError(
            f"{msg.op}: payload is {type(msg.payload).__name__}, "
            f"expected {payload_type.__name__}"
        )
    try:
        return handler(ctx, msg.payload)
    except Exception as err:
        err.add_note(
            f"op={msg.op} correlation_id={msg.correlation_id} "
            f"household_id={msg.household_id} message_id={msg.message_id}"
        )
        raise


def emit_event(ctx: DispatchContext, event: Message) -> None:
    """Fan a past-tense EVENT to its subscribers — synchronous, no reply.

    Isolation (S3): a reacting subscriber must not fail the committed emitter,
    so its exception is surfaced (``record_exception_panel``), never raised.
    """
    observability.record_event(
        event.op, event.correlation_id, event.household_id
    )
    for subscriber in SUBSCRIBERS.get(event.op, ()):
        try:
            subscriber(ctx, event.payload)
        except Exception as err:  # noqa: BLE001 — isolation boundary, surfaced
            record_exception_panel(ctx, event.op, err)


def record_exception_panel(
    ctx: DispatchContext, op: str, err: Exception
) -> None:
    """Surface an event-subscriber failure without failing the emitter.

    Surfaced to the in-process log (phase-2 panel reads it) and structlog —
    visible on the dashboard (dashboard-first), never silenced.
    """
    observability.record_subscriber_failure(op, err)
    logger.warning(
        "event_subscriber_failed",
        op=op,
        error=str(err),
        error_type=type(err).__name__,
        actor_id=ctx.actor_id,
    )
