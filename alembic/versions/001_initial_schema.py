"""Initial schema — entity graph, security master, lot ledger, workflow catalog."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("entity_id"),
    )
    op.create_index("ix_entities_entity_type", "entities", ["entity_type"])
    op.create_index("ix_entities_household_id", "entities", ["household_id"])

    op.create_table(
        "securities",
        sa.Column("security_id", sa.String(length=64), nullable=False),
        sa.Column("cusip", sa.String(length=16), nullable=True),
        sa.Column("isin", sa.String(length=16), nullable=True),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("tax_character", sa.String(length=32), nullable=False),
        sa.Column("liquidity_tier", sa.Integer(), nullable=False),
        sa.Column("wash_sale_substitute_group", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("security_id"),
    )
    op.create_index("ix_securities_cusip", "securities", ["cusip"])
    op.create_index("ix_securities_isin", "securities", ["isin"])
    op.create_index("ix_securities_ticker", "securities", ["ticker"])

    op.create_table(
        "entity_relationships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["entities.entity_id"]),
        sa.ForeignKeyConstraint(["target_id"], ["entities.entity_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entity_relationships_source_id", "entity_relationships", ["source_id"])
    op.create_index("ix_entity_relationships_target_id", "entity_relationships", ["target_id"])

    op.create_table(
        "lots",
        sa.Column("lot_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("security_id", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("cost_basis_per_share", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("wash_sale_chain_id", sa.String(length=64), nullable=True),
        sa.Column("is_restricted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["entities.entity_id"]),
        sa.ForeignKeyConstraint(["security_id"], ["securities.security_id"]),
        sa.PrimaryKeyConstraint("lot_id"),
    )
    op.create_index("ix_lots_account_id", "lots", ["account_id"])
    op.create_index("ix_lots_security_id", "lots", ["security_id"])

    op.create_table(
        "workflow_definitions",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("owner", sa.String(length=64), nullable=False),
        sa.Column("inputs", sa.Text(), nullable=False),
        sa.Column("outputs", sa.Text(), nullable=False),
        sa.Column("sla_hours", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("name"),
    )

    op.create_table(
        "schema_migration_meta",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("revision", sa.String(length=64), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("schema_migration_meta")
    op.drop_table("workflow_definitions")
    op.drop_table("lots")
    op.drop_table("entity_relationships")
    op.drop_table("securities")
    op.drop_table("entities")
