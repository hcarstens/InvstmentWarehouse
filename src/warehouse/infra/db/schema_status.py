"""Schema and migration status for the dashboard."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

from warehouse.infra.db.engine import create_db_engine
from warehouse.infra.db.migrate import current_revision
from warehouse.infra.db.models import (
    EntityRelationshipRow,
    EntityRow,
    IngestRunRow,
    LotRow,
    MarketPriceRow,
    ReconciliationBreakRow,
    SchemaMigrationMetaRow,
    SecurityRow,
    WorkflowDefinitionRow,
)

HEAD_REVISION = "008_recon_break_type"

TRACKED_TABLES: tuple[type[DeclarativeBase], ...] = (
    EntityRow,
    EntityRelationshipRow,
    SecurityRow,
    LotRow,
    WorkflowDefinitionRow,
    IngestRunRow,
    ReconciliationBreakRow,
    MarketPriceRow,
)


class TableStatus(BaseModel):
    name: str
    row_count: int


class SchemaStatus(BaseModel):
    current_revision: str | None
    head_revision: str
    is_current: bool
    last_applied_at: datetime | None
    tables: list[TableStatus]
    error: str | None = None


def _last_applied_at(session: Session) -> datetime | None:
    return session.scalar(
        select(SchemaMigrationMetaRow.applied_at)
        .order_by(SchemaMigrationMetaRow.applied_at.desc())
        .limit(1)
    )


def build_schema_status(engine: Engine | None = None) -> SchemaStatus:
    eng = engine or create_db_engine()
    try:
        revision = current_revision(eng)
        with Session(eng) as session:
            tables: list[TableStatus] = []
            if revision:
                for model in TRACKED_TABLES:
                    count = session.scalar(
                        select(func.count()).select_from(model)
                    )
                    tables.append(
                        TableStatus(
                            name=model.__tablename__, row_count=int(count or 0)
                        )
                    )
                last_at = _last_applied_at(session)
            else:
                last_at = None

            return SchemaStatus(
                current_revision=revision,
                head_revision=HEAD_REVISION,
                is_current=revision == HEAD_REVISION,
                last_applied_at=last_at,
                tables=tables,
            )
    except Exception as err:
        return SchemaStatus(
            current_revision=None,
            head_revision=HEAD_REVISION,
            is_current=False,
            last_applied_at=None,
            tables=[],
            error=str(err),
        )


def database_is_initialized(engine: Engine | None = None) -> bool:
    eng = engine or create_db_engine()
    with eng.connect() as conn:
        return "entities" in inspect(conn).get_table_names()
