"""Price/mark history — composite PK ``(security_id, as_of_date)`` (pv2).

Retires the single-mark ``MarketPriceRow`` assumption (review M3 caveat): a
security now carries a dated series, and ``list_lot_positions`` selects the mark
AT OR BEFORE ``as_of`` (no future-mark leakage). SQLite cannot alter a primary
key in place, so the tiny mark table is recreated; ``seed_market_prices``
re-inserts the demo marks on the next bootstrap (dev SQLite, Phases 0–4).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009_market_price_history"
down_revision: str | None = "008_recon_break_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("market_prices")
    op.create_table(
        "market_prices",
        sa.Column("security_id", sa.String(length=64), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["securities.security_id"]),
        sa.PrimaryKeyConstraint("security_id", "as_of_date"),
    )


def downgrade() -> None:
    op.drop_table("market_prices")
    op.create_table(
        "market_prices",
        sa.Column("security_id", sa.String(length=64), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["securities.security_id"]),
        sa.PrimaryKeyConstraint("security_id"),
    )
