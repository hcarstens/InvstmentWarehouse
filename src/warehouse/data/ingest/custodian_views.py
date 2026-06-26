"""Custodian-scoped position and ingest views."""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.data.ingest.runner import IngestRunSummary, list_ingest_runs
from warehouse.data.ledger.views import LotPositionView, list_lot_positions
from warehouse.infra.db.models import EntityRelationshipRow, EntityRow
from warehouse.models.entities import EntityType, RelationshipType


class CustodianSummary(BaseModel):
    custodian_id: str
    name: str


def list_custodians(session: Session) -> list[CustodianSummary]:
    rows = session.scalars(
        select(EntityRow).where(
            EntityRow.entity_type == EntityType.CUSTODIAN.value
        )
    ).all()
    return [
        CustodianSummary(custodian_id=r.entity_id, name=r.name) for r in rows
    ]


def accounts_for_custodian(session: Session, custodian_id: str) -> list[str]:
    rows = session.scalars(
        select(EntityRelationshipRow.source_id).where(
            EntityRelationshipRow.target_id == custodian_id,
            EntityRelationshipRow.relationship_type
            == RelationshipType.CUSTODIED_AT.value,
        )
    ).all()
    return list(rows)


def list_lot_positions_for_custodian(
    session: Session,
    *,
    household_id: str,
    custodian_id: str,
) -> list[LotPositionView]:
    account_ids = set(accounts_for_custodian(session, custodian_id))
    positions = list_lot_positions(session, household_id=household_id)
    return [p for p in positions if p.account_id in account_ids]


def list_ingest_runs_for_custodian(
    session: Session,
    custodian_id: str,
    limit: int = 10,
) -> list[IngestRunSummary]:
    runs = list_ingest_runs(session, limit=limit * 3)
    return [r for r in runs if r.custodian_id == custodian_id][:limit]
