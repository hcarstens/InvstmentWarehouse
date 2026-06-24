"""ORM models — entity graph, security master, lot ledger."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from warehouse.infra.db.base import Base


class EntityRow(Base):
    __tablename__ = "entities"

    entity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    household_id: Mapped[str | None] = mapped_column(String(64), index=True)


class EntityRelationshipRow(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)


class SecurityRow(Base):
    __tablename__ = "securities"

    security_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cusip: Mapped[str | None] = mapped_column(String(16), index=True)
    isin: Mapped[str | None] = mapped_column(String(16), index=True)
    ticker: Mapped[str | None] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    tax_character: Mapped[str] = mapped_column(String(32), nullable=False)
    liquidity_tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    wash_sale_substitute_group: Mapped[str | None] = mapped_column(String(64))


class LotRow(Base):
    __tablename__ = "lots"

    lot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    security_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cost_basis_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False)
    wash_sale_chain_id: Mapped[str | None] = mapped_column(String(64))
    is_restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class WorkflowDefinitionRow(Base):
    __tablename__ = "workflow_definitions"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner: Mapped[str] = mapped_column(String(64), nullable=False)
    inputs: Mapped[str] = mapped_column(Text, nullable=False)
    outputs: Mapped[str] = mapped_column(Text, nullable=False)
    sla_hours: Mapped[int | None] = mapped_column(Integer)


class SchemaMigrationMetaRow(Base):
    """Tracks last applied migration for dashboard display."""

    __tablename__ = "schema_migration_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    revision: Mapped[str] = mapped_column(String(64), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class IngestRunRow(Base):
    __tablename__ = "ingest_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    custodian_id: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    rows_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)


class CustodianPositionRow(Base):
    __tablename__ = "custodian_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ingest_runs.run_id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    security_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)


class ReconciliationBreakRow(Base):
    __tablename__ = "reconciliation_breaks"

    break_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ingest_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ingest_runs.run_id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    security_id: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    entry_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    household_id: Mapped[str | None] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class DailyRefreshRunRow(Base):
    __tablename__ = "daily_refresh_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    household_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class DailyRefreshStepRow(Base):
    __tablename__ = "daily_refresh_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    refresh_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("daily_refresh_runs.run_id"), nullable=False, index=True
    )
    step_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    detail: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)


class MarketPriceRow(Base):
    __tablename__ = "market_prices"

    security_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("securities.security_id"), primary_key=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
