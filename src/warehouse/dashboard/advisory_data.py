"""Advisory dashboard — ``pm.advise`` composite via messaging dispatch."""

from __future__ import annotations

from pydantic import BaseModel

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.dashboard.phase3_data import load_phase3_dashboard
from warehouse.decision.pm import build_working_set
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging import (
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
)
from warehouse.messaging.payloads import AdviceBundle


class AdvisoryDashboardData(BaseModel):
    household_id: str
    correlation_id: str
    bundle: AdviceBundle | None
    panel_status: str = "stub"
    error: str | None = None


def load_advisory_dashboard(
    household_id: str = DEMO_HOUSEHOLD_ID,
) -> AdvisoryDashboardData:
    correlation_id = "advisory-dashboard"
    try:
        bootstrap_database(seed=True)
        # phase3 → phase2 ensures demo ingest + decision runs exist.
        load_phase3_dashboard()
        with session_scope() as session:
            # Single working-set assembly path (shared with the rebalance
            # advisory workflow) — no duplicate manifest construction.
            payload = build_working_set(session, household_id)
            ctx = DispatchContext(
                session=session,
                actor_id="dashboard:advisory",
                correlation_id=correlation_id,
            )
            bundle = dispatch_message(
                ctx,
                Message(
                    op="pm.advise",
                    kind=Kind.EVALUATE,
                    payload=payload,
                    correlation_id=correlation_id,
                    household_id=household_id,
                ),
            )
        if not isinstance(bundle, AdviceBundle):
            raise TypeError(
                f"pm.advise returned {type(bundle).__name__}, "
                "expected AdviceBundle"
            )
        return AdvisoryDashboardData(
            household_id=household_id,
            correlation_id=correlation_id,
            bundle=bundle,
            panel_status="live",
        )
    except Exception as err:
        return AdvisoryDashboardData(
            household_id=household_id,
            correlation_id=correlation_id,
            bundle=None,
            error=str(err),
        )
