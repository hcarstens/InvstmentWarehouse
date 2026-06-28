"""Advisory dashboard — ``pm.advise`` composite via messaging dispatch."""

from __future__ import annotations

from pydantic import BaseModel

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.config import get_settings
from warehouse.dashboard.phase3_data import load_phase3_dashboard
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.ips.store import load_ips
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging import (
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
)
from warehouse.messaging.payloads import AdviceBundle, PmAdvisePayload
from warehouse.research.risk.adapters.ledger import build_household_manifest
from warehouse.research.risk.models import (
    RiskHorizon,
    RiskRequest,
    ScenarioSet,
)


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
        load_phase3_dashboard()
        settings = get_settings()
        manifest = build_household_manifest(household_id)
        with session_scope() as session:
            positions = list_lot_positions(session, household_id=household_id)
            ips = load_ips(session, household_id)
            if ips is None:
                raise ValueError(f"No IPS for household {household_id}")
            ctx = DispatchContext(
                session=session,
                actor_id="dashboard:advisory",
                correlation_id=correlation_id,
            )
            request = RiskRequest(
                horizon=RiskHorizon.parse(
                    settings.risk_dashboard_horizon_years
                ),
                notional_usd=manifest.notional_usd,
                run_scenarios=ScenarioSet.NONE,
            )
            bundle = dispatch_message(
                ctx,
                Message(
                    op="pm.advise",
                    kind=Kind.EVALUATE,
                    payload=PmAdvisePayload(
                        household_id=household_id,
                        positions=positions,
                        ips=ips,
                        manifest=manifest.portfolio,
                        request=request,
                    ),
                    correlation_id=correlation_id,
                    household_id=household_id,
                ),
            )
        assert isinstance(bundle, AdviceBundle)
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
