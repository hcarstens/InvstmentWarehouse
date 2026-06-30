"""rw6 — generalize approval subject (optimization | report).

Adds ``subject_type`` / ``subject_id`` to ``approval_requests`` and relaxes
``optimization_run_id`` to nullable so report-document approvals (which carry a
report ``snapshot_id`` in ``subject_id``) can reuse the same table. Existing
rows are back-filled as ``subject_type='optimization'``,
``subject_id=optimization_run_id``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_approval_report_subject"
down_revision: str | None = "006_reporting_realized"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite cannot ALTER a column to drop NOT NULL in place — recreate via
    # batch mode, which preserves the existing FK on optimization_run_id.
    with op.batch_alter_table("approval_requests") as batch:
        batch.add_column(
            sa.Column(
                "subject_type",
                sa.String(length=16),
                nullable=False,
                server_default="optimization",
            )
        )
        batch.add_column(
            sa.Column("subject_id", sa.String(length=64), nullable=True)
        )
        batch.alter_column("optimization_run_id", nullable=True)

    op.create_index(
        "ix_approval_requests_subject_type",
        "approval_requests",
        ["subject_type"],
    )
    op.create_index(
        "ix_approval_requests_subject_id",
        "approval_requests",
        ["subject_id"],
    )
    # Back-fill: existing rows are all optimization subjects.
    op.execute(
        "UPDATE approval_requests "
        "SET subject_id = optimization_run_id "
        "WHERE subject_id IS NULL"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_approval_requests_subject_id",
        table_name="approval_requests",
    )
    op.drop_index(
        "ix_approval_requests_subject_type",
        table_name="approval_requests",
    )
    with op.batch_alter_table("approval_requests") as batch:
        batch.alter_column("optimization_run_id", nullable=False)
        batch.drop_column("subject_id")
        batch.drop_column("subject_type")
