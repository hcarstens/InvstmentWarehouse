"""Rebalance advisory — ledger positions → PM working set → pm.advise.

Advisory half of the rebalance loop; does not persist or stage orders.
"""

from __future__ import annotations

from typing import cast
from uuid import uuid4

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


def run_rebalance_advisory(
    session: Session,
    household_id: str,
    *,
    correlation_id: str | None = None,
    actor_id: str = "system:rebalance_advisory",
) -> AdviceBundle:
    """Chain ``ledger.positions`` → working set → ``pm.advise``."""
    cid = correlation_id or f"advisory_{uuid4().hex[:12]}"
    ctx = DispatchContext(
        session=session, actor_id=actor_id, correlation_id=cid
    )

    position_set = cast(
        PositionSet,
        dispatch_message(
            ctx,
            Message(
                op="ledger.positions",
                kind=Kind.QUERY,
                payload=LedgerPositionsPayload(household_id=household_id),
                correlation_id=cid,
                household_id=household_id,
            ),
        ),
    )
    payload = build_working_set(
        session,
        household_id,
        positions=position_set.positions,
    )
    bundle = dispatch_message(
        ctx,
        Message(
            op="pm.advise",
            kind=Kind.EVALUATE,
            payload=PmAdvisePayload.model_validate(payload.model_dump()),
            correlation_id=cid,
            household_id=household_id,
        ),
    )
    assert isinstance(bundle, AdviceBundle)
    assert bundle.narrative is not None
    assert bundle.narrative.correlation_id == cid
    return bundle
