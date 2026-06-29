"""Reporting-owned tax scenario entry points (st6c)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from warehouse.config import Settings, get_settings
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.tax.scenarios import TaxScenarioOverlays
from warehouse.reporting.tax.compute import compute_reporting_tax_scenario


class ReportingTaxResult(BaseModel):
    """Frozen reporting-plane tax scenario rollup."""

    model_config = ConfigDict(frozen=True)

    overlays: TaxScenarioOverlays
    baseline_tax: Decimal
    scenario_tax: Decimal
    tax_delta: Decimal


def run_reporting_tax_scenario(
    session: Session,
    household_id: str,
    *,
    scenario_name: str,
    overlays: TaxScenarioOverlays | None = None,
    settings: Settings | None = None,
    as_of: date | None = None,
) -> ReportingTaxResult:
    """Compute and persist a reporting-owned tax scenario run."""
    from warehouse.infra.db.models import TaxScenarioRunRow

    cfg = settings or get_settings()
    policy = overlays or TaxScenarioOverlays()
    positions = list_lot_positions(session, household_id=household_id)
    if not positions:
        raise ValueError(f"No positions for household {household_id}")

    baseline, scenario, delta = compute_reporting_tax_scenario(
        positions,
        policy,
        as_of=as_of or date.today(),
        settings=cfg,
    )
    run_id = f"rpt_tax_{uuid4().hex[:12]}"
    created = datetime.now(UTC)
    session.add(
        TaxScenarioRunRow(
            run_id=run_id,
            household_id=household_id,
            scenario_name=scenario_name,
            overlays_json=json.dumps(policy.model_dump(mode="json")),
            baseline_tax=baseline,
            scenario_tax=scenario,
            tax_delta=delta,
            created_at=created,
        )
    )
    return ReportingTaxResult(
        overlays=policy,
        baseline_tax=baseline,
        scenario_tax=scenario,
        tax_delta=delta,
    )
