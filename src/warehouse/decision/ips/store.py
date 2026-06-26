"""IPS persistence and loading."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.infra.db.models import IpsPolicyRow


def row_to_ips(row: IpsPolicyRow) -> InvestmentPolicyStatement:
    allocation = json.loads(row.allocation_json)
    restricted = json.loads(row.restricted_json)
    return InvestmentPolicyStatement(
        ips_id=row.ips_id,
        household_id=row.household_id,
        version=row.version,
        effective_date=row.effective_date,
        allocation_targets=[AllocationTarget(**item) for item in allocation],
        restricted_securities=restricted,
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
        )
    )
