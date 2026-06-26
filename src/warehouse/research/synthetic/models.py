"""Shape B models — household graph, lots, alternatives sub-ledger."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from warehouse.research.risk.models import AssetPortfolio


class SyntheticAccount(BaseModel):
    account_id: str
    household_id: str
    name: str
    account_type: str


class SyntheticLot(BaseModel):
    lot_id: str
    account_id: str
    ticker: str
    asset_class: str
    quantity: Decimal
    cost_basis_per_share: Decimal
    market_price: Decimal
    acquisition_date: date
    is_loss_lot: bool = False
    concentration_issuer: str | None = None


class SyntheticAltCall(BaseModel):
    event_id: str
    holding_id: str
    event_date: date
    amount: Decimal


class SyntheticAltHolding(BaseModel):
    holding_id: str
    household_id: str
    entity_id: str
    name: str
    asset_type: str
    committed_capital: Decimal
    called_capital: Decimal
    unfunded_capital: Decimal
    current_nav: Decimal
    last_mark_date: date
    liquidity_tier: int = 3
    scheduled_calls: list[SyntheticAltCall] = Field(default_factory=list)


class ProvenanceManifest(BaseModel):
    generator_version: str
    seed: int
    cohort_id: str
    axiom_set_hash: str
    rung: int
    ips_scope: str = "investable"
    tension_tags: list[str] = Field(default_factory=list)
    stage_hashes: list[str] = Field(default_factory=list)


class HouseholdFixture(BaseModel):
    """Shape B — full synthetic household for optimizer / recon / risk projection."""

    household_id: str
    provenance: ProvenanceManifest
    accounts: list[SyntheticAccount]
    lots: list[SyntheticLot]
    alternative_holdings: list[SyntheticAltHolding]
    asset_portfolio: AssetPortfolio | None = None
    total_nav_usd: Decimal
