"""IPS persistence and loading."""

from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.decision.ips import (
    DEFAULT_CONCENTRATION_LIMIT,
    AllocationTarget,
    InvestmentPolicyStatement,
)
from warehouse.decision.ips.sleeves import parse_ips_sleeve
from warehouse.infra.db.models import IpsPolicyRow

_CONSTRAINT_KEYS = (
    "concentration_limit_pct",
    "liquidity_tier_min_pct",
    "turnover_budget_pct",
)


def _decimal_or_none(value: object | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _constraints_from_json(raw: str) -> dict[str, Decimal | None]:
    if not raw or raw == "{}":
        return {}
    data = json.loads(raw)
    return {
        key: _decimal_or_none(data.get(key))
        for key in _CONSTRAINT_KEYS
        if key in data
    }


def _constraints_to_json(ips: InvestmentPolicyStatement) -> str:
    payload: dict[str, str] = {
        "concentration_limit_pct": str(ips.concentration_limit_pct),
    }
    if ips.liquidity_tier_min_pct is not None:
        payload["liquidity_tier_min_pct"] = str(ips.liquidity_tier_min_pct)
    if ips.turnover_budget_pct is not None:
        payload["turnover_budget_pct"] = str(ips.turnover_budget_pct)
    return json.dumps(payload)


def row_to_ips(row: IpsPolicyRow) -> InvestmentPolicyStatement:
    allocation = json.loads(row.allocation_json)
    restricted = json.loads(row.restricted_json)
    constraints = _constraints_from_json(row.constraints_json)
    raw_concentration = constraints.get("concentration_limit_pct")
    concentration = (
        raw_concentration
        if raw_concentration is not None
        else DEFAULT_CONCENTRATION_LIMIT
    )
    return InvestmentPolicyStatement(
        ips_id=row.ips_id,
        household_id=row.household_id,
        version=row.version,
        effective_date=row.effective_date,
        allocation_targets=[
            AllocationTarget(
                **{
                    **item,
                    "asset_class": parse_ips_sleeve(item["asset_class"]),
                }
            )
            for item in allocation
        ],
        restricted_securities=restricted,
        concentration_limit_pct=concentration,
        liquidity_tier_min_pct=constraints.get("liquidity_tier_min_pct"),
        turnover_budget_pct=constraints.get("turnover_budget_pct"),
    )


def load_ips(
    session: Session, household_id: str
) -> InvestmentPolicyStatement | None:
    row = session.scalar(
        select(IpsPolicyRow)
        .where(IpsPolicyRow.household_id == household_id)
        .order_by(IpsPolicyRow.version.desc())
        .limit(1)
    )
    return row_to_ips(row) if row else None


def save_ips(session: Session, ips: InvestmentPolicyStatement) -> None:
    session.merge(
        IpsPolicyRow(
            ips_id=ips.ips_id,
            household_id=ips.household_id,
            version=ips.version,
            effective_date=ips.effective_date,
            allocation_json=json.dumps(
                [t.model_dump(mode="json") for t in ips.allocation_targets]
            ),
            restricted_json=json.dumps(ips.restricted_securities),
            constraints_json=_constraints_to_json(ips),
        )
    )
