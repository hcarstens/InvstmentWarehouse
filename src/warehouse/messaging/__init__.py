"""In-process messaging protocol — typed requests to one handler.

Public surface (``docs/messaging_protocol.md``). m0a ships the core
substrate; handler wrappers and payloads register in m0b.
"""

from warehouse.messaging.core import (
    REGISTRY,
    SUBSCRIBERS,
    Handler,
    Subscriber,
    dispatch_message,
    dispatch_typed,
    emit_event,
    register,
    subscribe,
)
from warehouse.messaging.models import (
    PROTOCOL_VERSION,
    DispatchContext,
    Kind,
    Message,
)

__all__ = [
    "PROTOCOL_VERSION",
    "DispatchContext",
    "Handler",
    "Kind",
    "Message",
    "REGISTRY",
    "SUBSCRIBERS",
    "Subscriber",
    "dispatch_message",
    "dispatch_typed",
    "emit_event",
    "register",
    "subscribe",
]
