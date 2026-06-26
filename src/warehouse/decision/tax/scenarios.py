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


def _baseline_tax(
    positions: list[LotPositionView], settings: Settings
) -> Decimal:
    taxable_gains = sum(
        (
            p.unrealized_gain
            for p in positions
            if p.unrealized_gain and p.unrealized_gain > 0
        ),
        Decimal("0"),
    )
    ltcg = Decimal(str(settings.fed_ltcg_rate))
    return taxable_gains * ltcg


def _scenario_tax(
    positions: list[LotPositionView],
    settings: Settings,
    overlays: TaxScenarioOverlays,
) -> Decimal:
    taxable_gains = sum(
        (
            p.unrealized_gain
            for p in positions
            if p.unrealized_gain and p.unrealized_gain > 0
        ),
        Decimal("0"),
    )
    ltcg = Decimal(str(settings.fed_ltcg_rate))
    tax = taxable_gains * ltcg

    if overlays.apply_niit:
        niit = Decimal(str(settings.niit_rate))
        tax += taxable_gains * niit

    if overlays.apply_amt:
        amt = Decimal(str(settings.amt_rate))
        tax += taxable_gains * amt

    if overlays.qsbs_exclusion_pct > 0:
        tax *= Decimal("1") - overlays.qsbs_exclusion_pct

    if overlays.trust_dni_rate > 0:
        tax *= Decimal("1") - overlays.trust_dni_rate

    return tax


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

    baseline = _baseline_tax(positions, cfg)
    scenario = _scenario_tax(positions, cfg, policy)
    delta = scenario - baseline

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
