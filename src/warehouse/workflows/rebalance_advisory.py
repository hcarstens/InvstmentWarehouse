"""Rebalance advisory — orchestrator gate → Portfolio Manager.

Advisory half of the rebalance loop; does not persist or stage orders.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from warehouse.messaging.payloads import AdviceBundle
from warehouse.orchestrator import (
    OrchestratorIntent,
    OrchestratorRequest,
    receive_request,
)


def run_rebalance_advisory(
    session: Session,
    household_id: str,
    *,
    correlation_id: str | None = None,
    actor_id: str = "system:rebalance_advisory",
) -> AdviceBundle:
    """Route through the Office Manager gate to ``pm.advise``."""
    response = receive_request(
        session,
        OrchestratorRequest(
            intent=OrchestratorIntent.REBALANCE_ADVISORY,
            household_id=household_id,
            correlation_id=correlation_id or f"advisory_{uuid4().hex[:12]}",
            actor_id=actor_id,
        ),
    )
    if response.status != "completed" or response.result is None:
        msg = response.error.message if response.error else "advisory failed"
        raise RuntimeError(
            f"rebalance advisory failed for {household_id}: {msg} "
            f"(correlation_id={response.correlation_id})"
        )
    return response.result
