"""Tax scenario overlays — AMT, NIIT, QSBS, trust DNI depth."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.config import Settings, get_settings
from warehouse.data.ledger.views import LotPositionView, list_lot_positions


class TaxScenarioOverlays(BaseModel):
    apply_niit: bool = True
    apply_amt: bool = False
    qsbs_exclusion_pct: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    trust_dni_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)


class TaxScenarioRunView(BaseModel):
    run_id: str
    household_id: str
    scenario_name: str
    overlays: TaxScenarioOverlays
    baseline_tax: Decimal
    scenario_tax: Decimal
    tax_delta: Decimal
    created_at: datetime


class TaxScenarioResult(BaseModel):
    """Session-less after-tax scenario — baseline vs overlay + delta."""

    overlays: TaxScenarioOverlays
    baseline_tax: Decimal
    scenario_tax: Decimal
    tax_delta: Decimal


def evaluate_tax_scenario(
    positions: list[LotPositionView],
    overlays: TaxScenarioOverlays | None = None,
    *,
    settings: Settings | None = None,
) -> TaxScenarioResult:
    """Pure after-tax comparison — stubbed to zero pending real estimates.

    ``run_tax_scenario`` wraps this and persists for the dashboard/CLI.
    See ``TODO.md`` — Tax scenario engine (estimate).
    """
    del positions, settings  # reserved for threshold-aware implementation
    policy = overlays or TaxScenarioOverlays()
    zero = Decimal("0")
    return TaxScenarioResult(
        overlays=policy,
        baseline_tax=zero,
        scenario_tax=zero,
        tax_delta=zero,
    )


def run_tax_scenario(
    session: Session,
    household_id: str,
    *,
    scenario_name: str,
    overlays: TaxScenarioOverlays | None = None,
    settings: Settings | None = None,
) -> TaxScenarioRunView:
    cfg = settings or get_settings()
    policy = overlays or TaxScenarioOverlays()
    positions = list_lot_positions(session, household_id=household_id)
    if not positions:
        raise ValueError(f"No positions for household {household_id}")

    result = evaluate_tax_scenario(positions, policy, settings=cfg)
    baseline = result.baseline_tax
    scenario = result.scenario_tax
    delta = result.tax_delta

    run_id = f"tax_{uuid4().hex[:12]}"
    created = datetime.now(UTC)
    from warehouse.infra.db.models import TaxScenarioRunRow

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

    return TaxScenarioRunView(
        run_id=run_id,
        household_id=household_id,
        scenario_name=scenario_name,
        overlays=policy,
        baseline_tax=baseline,
        scenario_tax=scenario,
        tax_delta=delta,
        created_at=created,
    )


def list_tax_scenarios(
    session: Session, household_id: str, limit: int = 5
) -> list[TaxScenarioRunView]:
    from warehouse.infra.db.models import TaxScenarioRunRow

    rows = session.scalars(
        select(TaxScenarioRunRow)
        .where(TaxScenarioRunRow.household_id == household_id)
        .order_by(TaxScenarioRunRow.created_at.desc())
        .limit(limit)
    ).all()
    views: list[TaxScenarioRunView] = []
    for row in rows:
        overlays = TaxScenarioOverlays(**json.loads(row.overlays_json))
        views.append(
            TaxScenarioRunView(
                run_id=row.run_id,
                household_id=row.household_id,
                scenario_name=row.scenario_name,
                overlays=overlays,
                baseline_tax=row.baseline_tax,
                scenario_tax=row.scenario_tax,
                tax_delta=row.tax_delta,
                created_at=row.created_at,
            )
        )
    return views
