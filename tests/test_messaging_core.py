"""m0a — messaging core: dispatch, registry, events, immutability (§4)."""

from collections.abc import Iterator

import pytest
from pydantic import BaseModel

from warehouse.messaging import (
    REGISTRY,
    SUBSCRIBERS,
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
    emit_event,
    register,
    subscribe,
)


class _Ping(BaseModel):
    value: int = 1


class _Pong(BaseModel):
    doubled: int


class _Other(BaseModel):
    x: str = "x"


@pytest.fixture(autouse=True)
def _isolate_registry() -> Iterator[None]:
    """Snapshot registry/subscribers so tests don't leak into each other."""
    reg = dict(REGISTRY)
    subs = {k: list(v) for k, v in SUBSCRIBERS.items()}
    yield
    REGISTRY.clear()
    REGISTRY.update(reg)
    SUBSCRIBERS.clear()
    SUBSCRIBERS.update(subs)


@pytest.fixture
def ctx() -> DispatchContext:
    # Core tests use dummy handlers that never touch the session.
    return DispatchContext(session=None)  # type: ignore[arg-type]


def _msg(op: str, payload: BaseModel, **kw) -> Message:
    return Message(
        op=op,
        kind=Kind.QUERY,
        payload=payload,
        correlation_id="corr-1",
        **kw,
    )


def test_unknown_op_raises_keyerror(ctx: DispatchContext) -> None:
    with pytest.raises(KeyError, match="unknown op: nope.missing"):
        dispatch_message(ctx, _msg("nope.missing", _Ping()))


def test_payload_type_mismatch_raises_typeerror(
    ctx: DispatchContext,
) -> None:
    register("t.ping", _Ping, lambda c, p: _Pong(doubled=2), Kind.QUERY)
    with pytest.raises(TypeError, match="expected _Ping"):
        dispatch_message(ctx, _msg("t.ping", _Other()))


def test_dispatch_returns_handler_result(ctx: DispatchContext) -> None:
    register(
        "t.ping", _Ping, lambda c, p: _Pong(doubled=p.value * 2), Kind.QUERY
    )
    result = dispatch_message(ctx, _msg("t.ping", _Ping(value=21)))
    assert isinstance(result, _Pong)
    assert result.doubled == 42


def test_payload_concrete_type_preserved(ctx: DispatchContext) -> None:
    """Envelope must not coerce a subclass payload to bare BaseModel."""
    seen: list[type] = []

    def _h(c: DispatchContext, p: _Ping) -> BaseModel:
        seen.append(type(p))
        return _Pong(doubled=0)

    register("t.ping", _Ping, _h, Kind.QUERY)
    dispatch_message(ctx, _msg("t.ping", _Ping()))
    assert seen == [_Ping]


def test_message_id_auto_stamped() -> None:
    msg = _msg("t.ping", _Ping())
    assert len(msg.message_id) == 32
    assert msg.message_id != _msg("t.ping", _Ping()).message_id


def test_handler_error_carries_context(ctx: DispatchContext) -> None:
    def _boom(c: DispatchContext, p: _Ping) -> BaseModel:
        raise ValueError("kaboom")

    register("t.boom", _Ping, _boom, Kind.COMMAND)
    with pytest.raises(ValueError) as exc:
        dispatch_message(
            ctx, _msg("t.boom", _Ping(), household_id="hh_1")
        )
    notes = " ".join(getattr(exc.value, "__notes__", []))
    assert "op=t.boom" in notes
    assert "correlation_id=corr-1" in notes
    assert "household_id=hh_1" in notes


def test_register_duplicate_op_raises() -> None:
    register("t.dup", _Ping, lambda c, p: _Pong(doubled=0), Kind.QUERY)
    with pytest.raises(ValueError, match="already registered"):
        register("t.dup", _Ping, lambda c, p: _Pong(doubled=0), Kind.QUERY)


def test_event_subscriber_failure_is_isolated(
    ctx: DispatchContext,
) -> None:
    """A failing subscriber must not fail the emitter; a good one runs."""
    ran: list[str] = []

    def _bad(c: DispatchContext, p: BaseModel) -> None:
        raise RuntimeError("subscriber down")

    def _good(c: DispatchContext, p: BaseModel) -> None:
        ran.append("good")

    subscribe("evt.thing", _bad)
    subscribe("evt.thing", _good)
    event = Message(
        op="evt.thing",
        kind=Kind.EVENT,
        payload=_Ping(),
        correlation_id="c",
    )
    emit_event(ctx, event)  # does not raise despite _bad failing
    assert ran == ["good"]
