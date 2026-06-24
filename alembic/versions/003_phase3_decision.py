"""Phase 3 — IPS, optimizer, approval, backtest tables."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_phase3"
down_revision: Union[str, None] = "002_phase2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ips_policies",
        sa.Column("ips_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.String(length=16), nullable=False),
        sa.Column("allocation_json", sa.Text(), nullable=False),
        sa.Column("restricted_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("ips_id"),
    )
    op.create_index("ix_ips_policies_household_id", "ips_policies", ["household_id"])

    op.create_table(
        "optimization_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("config_version", sa.String(length=32), nullable=False),
        sa.Column("estimated_tax_delta", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("binding_constraints_json", sa.Text(), nullable=False),
        sa.Column("input_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_optimization_runs_household_id", "optimization_runs", ["household_id"])

    op.create_table(
        "optimization_trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("lot_id", sa.String(length=64), nullable=True),
        sa.Column("security_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["optimization_runs.run_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_optimization_trades_run_id", "optimization_trades", ["run_id"])

    op.create_table(
        "approval_requests",
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("optimization_run_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reviewer_id", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["optimization_run_id"], ["optimization_runs.run_id"]),
        sa.PrimaryKeyConstraint("request_id"),
    )
    op.create_index("ix_approval_requests_household_id", "approval_requests", ["household_id"])

    op.create_table(
        "backtest_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("after_tax_return", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("baseline_after_tax_return", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("tax_delta", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("input_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_backtest_runs_household_id", "backtest_runs", ["household_id"])


def downgrade() -> None:
    op.drop_table("backtest_runs")
    op.drop_table("approval_requests")
    op.drop_table("optimization_trades")
    op.drop_table("optimization_runs")
    op.drop_table("ips_policies")
