"""Security master — instrument identity and attributes."""

from enum import StrEnum

from pydantic import BaseModel, Field


class AssetClass(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    FIXED_INCOME = "fixed_income"
    CASH = "cash"
    ALTERNATIVE = "alternative"


class TaxCharacter(StrEnum):
    ORDINARY = "ordinary"
    QUALIFIED_DIVIDEND = "qualified_dividend"
    LTCG = "ltcg"
    TAX_EXEMPT = "tax_exempt"
    REIT = "reit"


class Security(BaseModel):
    """Security master v0 — symbology and tax-relevant attributes."""

    security_id: str
    cusip: str | None = None
    isin: str | None = None
    ticker: str | None = None
    name: str
    asset_class: AssetClass
    tax_character: TaxCharacter
    liquidity_tier: int = Field(
        default=1, ge=1, le=5, description="1=most liquid"
    )
    wash_sale_substitute_group: str | None = None
