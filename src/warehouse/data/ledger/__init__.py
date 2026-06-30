"""Lot-level portfolio accounting — positions, cost basis, P&L."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Lot(BaseModel):
    """Account × Instrument × Lot — cost basis and wash-sale chain."""

    lot_id: str
    account_id: str
    security_id: str
    quantity: Decimal
    cost_basis_per_share: Decimal
    acquisition_date: date
    wash_sale_chain_id: str | None = None
    is_restricted: bool = False  # do-not-sell legacy lots


class Position(BaseModel):
    """Aggregated position view derived from lots."""

    account_id: str
    security_id: str
    quantity: Decimal
    total_cost_basis: Decimal
    market_value: Decimal | None = None
    unrealized_gain: Decimal | None = None


class LotLedger(BaseModel):
    """Collection of lots for an account with audit metadata."""

    account_id: str
    lots: list[Lot] = Field(default_factory=list)
    as_of_date: date


from warehouse.data.ledger.corporate_actions import (  # noqa: E402
    StockSplitAction,
    apply_stock_split,
    apply_stock_splits,
    oracle_stock_split_basis,
)
from warehouse.data.ledger.wash_chains import (  # noqa: E402
    WashSaleSellEvent,
    assign_wash_sale_chain_ids,
    substantially_identical_securities,
)

__all__ = [
    "Lot",
    "LotLedger",
    "Position",
    "StockSplitAction",
    "WashSaleSellEvent",
    "apply_stock_split",
    "apply_stock_splits",
    "assign_wash_sale_chain_ids",
    "oracle_stock_split_basis",
    "substantially_identical_securities",
]
