"""IPS policy constraint fields — concentration, liquidity, turnover."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_ips_constraints"
down_revision: str | None = "004_phase4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ips_policies",
        sa.Column(
            "constraints_json",
            sa.Text(),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("ips_policies", "constraints_json")
