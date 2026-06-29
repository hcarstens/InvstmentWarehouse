"""Reporting — persisted realized gain events for YTD performance."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_reporting_realized"
down_revision: str | None = "005_ips_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "realized_gain_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_realized_gain_events_household_id",
        "realized_gain_events",
        ["household_id"],
    )
    op.create_index(
        "ix_realized_gain_events_event_date",
        "realized_gain_events",
        ["event_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_realized_gain_events_event_date",
        table_name="realized_gain_events",
    )
    op.drop_index(
        "ix_realized_gain_events_household_id",
        table_name="realized_gain_events",
    )
    op.drop_table("realized_gain_events")
