"""m0d — events: in-process log, subscriber isolation, daily_refresh trace."""

from collections.abc import Iterator

import pytest

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.config import repo_root
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging import (
    SUBSCRIBERS,
    DispatchContext,
    Kind,
    Message,
    emit_event,
    observability,
    subscribe,
)
from warehouse.messaging.models import IngestCompleted
from warehouse.workflows.daily_refresh import run_daily_refresh


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    """Reset the in-process log + subscribers around each test."""
    subs = {k: list(v) for k, v in SUBSCRIBERS.items()}
    observability.clear()
    yield
    observability.clear()
    SUBSCRIBERS.clear()
    SUBSCRIBERS.update(subs)


def _ctx() -> DispatchContext:
    return DispatchContext(session=None)  # type: ignore[arg-type]


def test_emit_records_event_in_log() -> None:
    emit_event(
        _ctx(),
        Message(
            op="ingest.completed",
            kind=Kind.EVENT,
            payload=IngestCompleted(household_id="hh", run_id="r1", rows=2),
            correlation_id="corr-7",
            household_id="hh",
        ),
    )
    ops = [e.op for e in observability.recent_events()]
    assert "ingest.completed" in ops
    latest = observability.recent_events()[0]
    assert latest.correlation_id == "corr-7"
    assert latest.household_id == "hh"


def test_subscriber_failure_recorded_and_isolated() -> None:
    ran: list[str] = []

    def _bad(c: DispatchContext, p: object) -> None:
        raise RuntimeError("subscriber down")

    def _good(c: DispatchContext, p: object) -> None:
        ran.append("good")

    subscribe("order.filled", _bad)
    subscribe("order.filled", _good)
    emit_event(
        _ctx(),
        Message(
            op="order.filled",
            kind=Kind.EVENT,
            payload=IngestCompleted(household_id="hh", run_id="r", rows=0),
            correlation_id="c",
        ),
    )
    assert ran == ["good"]  # good subscriber still ran
    failures = observability.recent_failures()
    assert any(
        f.op == "order.filled" and f.error_type == "RuntimeError"
        for f in failures
    )


def test_daily_refresh_emits_traced_events() -> None:
    bootstrap_database(seed=True)
    schwab = repo_root() / "tests/fixtures/schwab_positions.csv"
    with session_scope() as session:
        result = run_daily_refresh(
            session,
            schwab,
            household_id=DEMO_HOUSEHOLD_ID,
            use_research_sandbox=False,
        )
    events = observability.recent_events()
    completed = [e for e in events if e.op == "ingest.completed"]
    assert completed
    # one workflow trace — event correlation_id == refresh run_id
    assert completed[0].correlation_id == result.run_id
