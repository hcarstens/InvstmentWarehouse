"""Advisory dashboard — routes through the Office Manager gate."""

from __future__ import annotations

from pydantic import BaseModel

from warehouse.config import get_settings
from warehouse.dashboard.phase3_data import load_phase3_dashboard
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging.payloads import AdviceBundle
from warehouse.orchestrator import (
    OrchestratorIntent,
    OrchestratorRequest,
    receive_request,
    recent_in_flight,
)
from warehouse.orchestrator.models import InFlightRecord


class AdvisoryDashboardData(BaseModel):
    household_id: str
    correlation_id: str
    bundle: AdviceBundle | None
    panel_status: str = "live"
    in_flight: list[InFlightRecord] = []
    error: str | None = None


def load_advisory_dashboard(
    household_id: str = DEMO_HOUSEHOLD_ID,
) -> AdvisoryDashboardData:
    correlation_id = "advisory-dashboard"
    try:
        bootstrap_database(seed=True)
        load_phase3_dashboard()
        get_settings()
        with session_scope() as session:
            response = receive_request(
                session,
                OrchestratorRequest(
                    intent=OrchestratorIntent.REBALANCE_ADVISORY,
                    household_id=household_id,
                    correlation_id=correlation_id,
                    actor_id="dashboard:advisory",
                ),
            )
        if response.status != "completed" or response.result is None:
            msg = (
                response.error.message
                if response.error
                else "advisory gate returned no result"
            )
            raise RuntimeError(msg)
        return AdvisoryDashboardData(
            household_id=household_id,
            correlation_id=response.correlation_id,
            bundle=response.result,
            in_flight=recent_in_flight(limit=10),
        )
    except Exception as err:
        return AdvisoryDashboardData(
            household_id=household_id,
            correlation_id=correlation_id,
            bundle=None,
            in_flight=recent_in_flight(limit=10),
            error=str(err),
        )
