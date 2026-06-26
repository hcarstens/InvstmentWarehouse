"""Phase 4 — OMS, solver comparison, alternatives, tax scenarios."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004_phase4"
down_revision: str | None = "003_phase3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "optimization_runs",
        sa.Column("solver_type", sa.String(length=16), nullable=False, server_default="heuristic"),
    )
    op.add_column(
        "optimization_runs",
        sa.Column("runtime_ms", sa.Integer(), nullable=True),
    )

    op.create_table(
        "staged_orders",
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("approval_request_id", sa.String(length=64), nullable=False),
        sa.Column("optimization_run_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("lot_id", sa.String(length=64), nullable=True),
        sa.Column("security_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.request_id"]),
        sa.ForeignKeyConstraint(["optimization_run_id"], ["optimization_runs.run_id"]),
        sa.PrimaryKeyConstraint("order_id"),
    )
    op.create_index("ix_staged_orders_household_id", "staged_orders", ["household_id"])
    op.create_index("ix_staged_orders_status", "staged_orders", ["status"])

    op.create_table(
        "solver_comparisons",
        sa.Column("comparison_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("heuristic_run_id", sa.String(length=64), nullable=False),
        sa.Column("mip_run_id", sa.String(length=64), nullable=False),
        sa.Column("heuristic_tax_delta", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("mip_tax_delta", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("heuristic_runtime_ms", sa.Integer(), nullable=False),
        sa.Column("mip_runtime_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["heuristic_run_id"], ["optimization_runs.run_id"]),
        sa.ForeignKeyConstraint(["mip_run_id"], ["optimization_runs.run_id"]),
        sa.PrimaryKeyConstraint("comparison_id"),
    )
    op.create_index("ix_solver_comparisons_household_id", "solver_comparisons", ["household_id"])

    op.create_table(
        "alternative_holdings",
        sa.Column("holding_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("committed_capital", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("called_capital", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("current_nav", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("last_mark_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("holding_id"),
    )
    op.create_index("ix_alternative_holdings_household_id", "alternative_holdings", ["household_id"])

    op.create_table(
        "alternative_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("holding_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["holding_id"], ["alternative_holdings.holding_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_alternative_events_holding_id", "alternative_events", ["holding_id"])

    op.create_table(
        "tax_scenario_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("scenario_name", sa.String(length=64), nullable=False),
        sa.Column("overlays_json", sa.Text(), nullable=False),
        sa.Column("baseline_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("scenario_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tax_delta", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_tax_scenario_runs_household_id", "tax_scenario_runs", ["household_id"])


def downgrade() -> None:
    op.drop_table("tax_scenario_runs")
    op.drop_table("alternative_events")
    op.drop_table("alternative_holdings")
    op.drop_table("solver_comparisons")
    op.drop_table("staged_orders")
    op.drop_column("optimization_runs", "runtime_ms")
    op.drop_column("optimization_runs", "solver_type")
