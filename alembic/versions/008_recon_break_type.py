"""Reconciliation break taxonomy — typed break_type column (qa1)."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_recon_break_type"
down_revision: str | None = "007_approval_report_subject"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reconciliation_breaks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "break_type",
                sa.String(length=32),
                nullable=False,
                server_default="quantity_mismatch",
            )
        )
    op.execute(
        "UPDATE reconciliation_breaks SET break_type = 'stale_as_of' "
        "WHERE description LIKE 'stale custodian file%'"
    )
    op.execute(
        "UPDATE reconciliation_breaks SET break_type = 'stale_as_of' "
        "WHERE description LIKE 'ledger has no market-price%'"
    )
    op.execute(
        "UPDATE reconciliation_breaks SET break_type = 'mixed_as_of' "
        "WHERE description LIKE 'mixed as_of_date%'"
    )
    op.execute(
        "UPDATE reconciliation_breaks SET break_type = 'ledger_only' "
        "WHERE description LIKE '%custodian=0, ledger=%'"
    )
    op.execute(
        "UPDATE reconciliation_breaks SET break_type = 'quantity_mismatch' "
        "WHERE description LIKE '%custodian=%' AND description LIKE '%ledger=%' "
        "AND description NOT LIKE '%custodian=0, ledger=%'"
    )


def downgrade() -> None:
    with op.batch_alter_table("reconciliation_breaks") as batch_op:
        batch_op.drop_column("break_type")
