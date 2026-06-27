"""Risk dashboard data — manifest → evaluate_risk → present."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from warehouse.config import get_settings
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.research.risk.adapters.ledger import build_household_manifest
from warehouse.research.risk.models import (
    AssetClass,
    ManifestOverlay,
    PortfolioRiskReport,
    RiskDeltas,
    RiskHorizon,
    RiskRequest,
    ScenarioSet,
)
from warehouse.research.risk.observability import (
    log_risk_evaluated,
    record_risk_failure,
)
from warehouse.research.risk.service import evaluate_risk


class RiskDashboardData(BaseModel):
    household_id: str
    horizon_years: Decimal
    notional_usd: Decimal | None
    report: PortfolioRiskReport | None
    source: str
    deltas: RiskDeltas | None = None
    error: str | None = None


_DEMO_OVERLAY = ManifestOverlay(
    label="reduce equity 10% → fixed income",
    weight_tilts={
        AssetClass.EQUITY: Decimal("-0.10"),
        AssetClass.FIXED_INCOME: Decimal("0.10"),
    },
)


def load_risk_dashboard(
    household_id: str = DEMO_HOUSEHOLD_ID,
    *,
    horizon_years: Decimal | None = None,
) -> RiskDashboardData:
    settings = get_settings()
    horizon = RiskHorizon.parse(
        horizon_years or settings.risk_dashboard_horizon_years
    )
    try:
        manifest = build_household_manifest(household_id)
        overlay = (
            _DEMO_OVERLAY if settings.risk_dashboard_demo_overlay else None
        )
        request = RiskRequest(
            horizon=horizon,
            notional_usd=manifest.notional_usd,
            run_scenarios=ScenarioSet.NONE,
            overlay=overlay,
        )
        result = evaluate_risk(request, manifest.portfolio)
        log_risk_evaluated(
            result,
            request=request,
            manifest=manifest.portfolio,
            surface="dashboard",
        )
        return RiskDashboardData(
            household_id=household_id,
            horizon_years=horizon.years,
            notional_usd=manifest.notional_usd,
            report=result.report,
            source=manifest.portfolio.source,
            deltas=result.deltas,
        )
    except Exception as err:
        record_risk_failure(
            err,
            surface="dashboard",
            household_id=household_id,
        )
        return RiskDashboardData(
            household_id=household_id,
            horizon_years=horizon.years,
            notional_usd=None,
            report=None,
            source="ledger",
            error=str(err),
        )
