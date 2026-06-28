"""Office Manager gate — receive, route to PM, respond (OM1–OM8)."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging import REGISTRY, Kind, observability
from warehouse.messaging.payloads import AdviceBundle
from warehouse.orchestrator import (
    OrchestratorIntent,
    OrchestratorRequest,
    receive_request,
    recent_in_flight,
)
from warehouse.orchestrator.registry import clear as clear_in_flight
from warehouse.workflows.rebalance_advisory import run_rebalance_advisory

DEMO = DEMO_HOUSEHOLD_ID


@pytest.fixture
def seeded() -> Iterator[None]:
    bootstrap_database(seed=True)
    clear_in_flight()
    yield
    clear_in_flight()


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    snapshot = dict(REGISTRY)
    observability.clear()
    yield
    REGISTRY.clear()
    REGISTRY.update(snapshot)
    observability.clear()


def test_gate_receives_and_responds_with_advice_bundle(seeded: None) -> None:
    with session_scope() as session:
        response = receive_request(
            session,
            OrchestratorRequest(
                intent=OrchestratorIntent.REBALANCE_ADVISORY,
                household_id=DEMO,
                correlation_id="gate-advisory-1",
            ),
        )
    assert response.status == "completed"
    assert response.correlation_id == "gate-advisory-1"
    assert response.assigned_actor == "portfolio_manager"
    assert isinstance(response.result, AdviceBundle)
    assert response.result.narrative is not None
    assert response.error is None


def test_gate_routes_only_through_pm_advise(seeded: None) -> None:
    seen_ops: list[str] = []
    original = REGISTRY["pm.advise"]

    def _spy_pm(ctx, payload):  # type: ignore[no-untyped-def]
        seen_ops.append("pm.advise")
        return original[1](ctx, payload)

    REGISTRY["pm.advise"] = (original[0], _spy_pm, Kind.EVALUATE)

    with session_scope() as session:
        receive_request(
            session,
            OrchestratorRequest(
                intent=OrchestratorIntent.REBALANCE_ADVISORY,
                household_id=DEMO,
                correlation_id="gate-route-1",
            ),
        )
    assert seen_ops == ["pm.advise"]


def test_failure_containment_structured_error(seeded: None) -> None:
    with (
        session_scope() as session,
        patch(
            "warehouse.orchestrator.gate.dispatch_message",
            side_effect=RuntimeError("internal pm leg failed"),
        ),
    ):
        response = receive_request(
            session,
            OrchestratorRequest(
                intent=OrchestratorIntent.REBALANCE_ADVISORY,
                household_id=DEMO,
                correlation_id="gate-fail-1",
            ),
        )
    assert response.status == "failed"
    assert response.error is not None
    assert response.error.correlation_id == "gate-fail-1"
    assert "pm.advise" not in response.error.message.lower()
    assert "internal" not in response.error.message.lower()


def test_in_flight_registry_records_request(seeded: None) -> None:
    with session_scope() as session:
        receive_request(
            session,
            OrchestratorRequest(
                intent=OrchestratorIntent.REBALANCE_ADVISORY,
                household_id=DEMO,
                correlation_id="gate-flight-1",
            ),
        )
    records = recent_in_flight(limit=5)
    assert records
    latest = records[0]
    assert latest.correlation_id == "gate-flight-1"
    assert latest.stage.value == "completed"
    assert latest.assigned_actor == "portfolio_manager"
    assert latest.elapsed_ms is not None


def test_rebalance_advisory_uses_gate(seeded: None) -> None:
    with session_scope() as session:
        bundle = run_rebalance_advisory(
            session, DEMO, correlation_id="workflow-gate-1"
        )
    assert bundle.narrative is not None
    assert bundle.narrative.correlation_id == "workflow-gate-1"
