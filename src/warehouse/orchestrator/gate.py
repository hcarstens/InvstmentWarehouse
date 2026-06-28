"""Office Manager gate — receive, route, respond (ℍ_OM / messaging §4.1).

Single entry for external callers. Routes to the Portfolio Manager via
``dispatch_message`` only — hub-and-spoke, no peer actor calls (OM5).
"""

from __future__ import annotations

import time
from typing import cast
from uuid import uuid4

import structlog
from sqlalchemy.orm import Session

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.decision.pm import build_working_set
from warehouse.messaging import (
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
)
from warehouse.messaging.payloads import (
    AdviceBundle,
    LedgerPositionsPayload,
    PmAdvisePayload,
    PositionSet,
)
from warehouse.orchestrator import registry as flight_registry
from warehouse.orchestrator.models import (
    InFlightStage,
    OrchestratorError,
    OrchestratorIntent,
    OrchestratorRequest,
    OrchestratorResponse,
)

logger = structlog.get_logger(__name__)

_ASSIGNED_ACTOR: dict[OrchestratorIntent, str] = {
    OrchestratorIntent.REBALANCE_ADVISORY: "portfolio_manager",
}

_GATE_FAILURE_MESSAGE = "The request could not be completed."


def receive_request(
    session: Session,
    request: OrchestratorRequest,
) -> OrchestratorResponse:
    """Single gate: receive a caller request and return a unified response."""
    correlation_id = request.correlation_id or f"orch_{uuid4().hex[:12]}"
    started = time.monotonic()
    flight_registry.start(request, correlation_id=correlation_id)

    actor = _ASSIGNED_ACTOR.get(request.intent)
    if actor is None:
        flight_registry.fail(correlation_id)
        return _failed_response(
            request,
            correlation_id=correlation_id,
            started=started,
            message="Unsupported request intent.",
        )

    try:
        flight_registry.advance(
            correlation_id,
            stage=InFlightStage.DISPATCHING,
            assigned_actor=actor,
        )
        if request.intent is OrchestratorIntent.REBALANCE_ADVISORY:
            bundle = _send_to_portfolio_manager(
                session,
                request,
                correlation_id=correlation_id,
            )
        else:
            raise AssertionError(f"unhandled routed intent: {request.intent}")

        flight_registry.complete(correlation_id)
        return OrchestratorResponse(
            correlation_id=correlation_id,
            intent=request.intent,
            household_id=request.household_id,
            status="completed",
            assigned_actor=actor,
            result=bundle,
            elapsed_ms=_elapsed_ms(started),
        )
    except Exception as err:
        logger.exception(
            "orchestrator_gate_failed",
            correlation_id=correlation_id,
            intent=request.intent.value,
            household_id=request.household_id,
            error_type=type(err).__name__,
        )
        flight_registry.fail(correlation_id)
        return _failed_response(
            request,
            correlation_id=correlation_id,
            started=started,
            message=_GATE_FAILURE_MESSAGE,
            assigned_actor=actor,
        )


def _send_to_portfolio_manager(
    session: Session,
    request: OrchestratorRequest,
    *,
    correlation_id: str,
) -> AdviceBundle:
    """Dispatch advisory work to ``pm.advise`` via messaging."""
    ctx = DispatchContext(
        session=session,
        actor_id=request.actor_id,
        correlation_id=correlation_id,
    )
    household_id = request.household_id

    position_set = cast(
        PositionSet,
        dispatch_message(
            ctx,
            Message(
                op="ledger.positions",
                kind=Kind.QUERY,
                payload=LedgerPositionsPayload(household_id=household_id),
                correlation_id=correlation_id,
                household_id=household_id,
            ),
        ),
    )
    payload = build_working_set(
        session,
        household_id,
        positions=position_set.positions,
        as_of_date=request.as_of_date,
    )
    if request.cohort_id is not None:
        payload = payload.model_copy(update={"cohort_id": request.cohort_id})

    bundle = dispatch_message(
        ctx,
        Message(
            op="pm.advise",
            kind=Kind.EVALUATE,
            payload=PmAdvisePayload.model_validate(payload.model_dump()),
            correlation_id=correlation_id,
            household_id=household_id,
        ),
    )
    if not isinstance(bundle, AdviceBundle):
        raise TypeError(
            f"pm.advise returned {type(bundle).__name__}, "
            f"expected AdviceBundle"
        )
    return bundle


def _failed_response(
    request: OrchestratorRequest,
    *,
    correlation_id: str,
    started: float,
    message: str,
    assigned_actor: str | None = None,
) -> OrchestratorResponse:
    return OrchestratorResponse(
        correlation_id=correlation_id,
        intent=request.intent,
        household_id=request.household_id,
        status="failed",
        assigned_actor=assigned_actor,
        error=OrchestratorError(
            correlation_id=correlation_id,
            message=message,
        ),
        elapsed_ms=_elapsed_ms(started),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
