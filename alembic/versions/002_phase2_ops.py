"""Phase 2 operational tables — ingest, reconciliation, audit, daily refresh."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002_phase2"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingest_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("custodian_id", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("rows_processed", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_table(
        "custodian_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ingest_run_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("security_id", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["ingest_run_id"], ["ingest_runs.run_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custodian_positions_ingest_run_id", "custodian_positions", ["ingest_run_id"])
    op.create_index("ix_custodian_positions_account_id", "custodian_positions", ["account_id"])
    op.create_index("ix_custodian_positions_security_id", "custodian_positions", ["security_id"])

    op.create_table(
        "reconciliation_breaks",
        sa.Column("break_id", sa.String(length=64), nullable=False),
        sa.Column("ingest_run_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("security_id", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["ingest_run_id"], ["ingest_runs.run_id"]),
        sa.PrimaryKeyConstraint("break_id"),
    )
    op.create_index(
        "ix_reconciliation_breaks_ingest_run_id", "reconciliation_breaks", ["ingest_run_id"]
    )
    op.create_index("ix_reconciliation_breaks_account_id", "reconciliation_breaks", ["account_id"])

    op.create_table(
        "audit_log",
        sa.Column("entry_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("entry_id"),
    )
    op.create_index("ix_audit_log_household_id", "audit_log", ["household_id"])

    op.create_table(
        "daily_refresh_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_daily_refresh_runs_household_id", "daily_refresh_runs", ["household_id"])

    op.create_table(
        "daily_refresh_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("refresh_run_id", sa.String(length=64), nullable=False),
        sa.Column("step_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["refresh_run_id"], ["daily_refresh_runs.run_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_daily_refresh_steps_refresh_run_id", "daily_refresh_steps", ["refresh_run_id"]
    )

    op.create_table(
        "market_prices",
        sa.Column("security_id", sa.String(length=64), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["securities.security_id"]),
        sa.PrimaryKeyConstraint("security_id"),
    )


def downgrade() -> None:
    op.drop_table("market_prices")
    op.drop_table("daily_refresh_steps")
    op.drop_table("daily_refresh_runs")
    op.drop_table("audit_log")
    op.drop_table("reconciliation_breaks")
    op.drop_table("custodian_positions")
    op.drop_table("ingest_runs")
