"""Performance, risk, and tax reporting views derived from lot ledger."""

from decimal import Decimal

from pydantic import BaseModel


class HouseholdPerformanceReport(BaseModel):
    household_id: str
    as_of_date: str
    total_market_value: Decimal
    unrealized_gain: Decimal
    realized_gain_ytd: Decimal
    after_tax_return_ytd: Decimal | None = None
