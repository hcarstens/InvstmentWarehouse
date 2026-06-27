"""IPS monitoring — drift vs strategic allocation and policy constraints."""

from decimal import Decimal

from pydantic import BaseModel, Field

from warehouse.decision.ips.sleeves import IpsSleeve

DEFAULT_CONCENTRATION_LIMIT = Decimal("0.25")


class AllocationTarget(BaseModel):
    asset_class: IpsSleeve
    min_weight: Decimal = Field(ge=0, le=1)
    max_weight: Decimal = Field(ge=0, le=1)
    target_weight: Decimal = Field(ge=0, le=1)


class InvestmentPolicyStatement(BaseModel):
    """Machine-readable IPS on the household graph — versioned, effective-dated."""

    ips_id: str
    household_id: str
    version: int
    effective_date: str
    allocation_targets: list[AllocationTarget]
    restricted_securities: list[str] = Field(default_factory=list)
    concentration_limit_pct: Decimal = Field(
        default=DEFAULT_CONCENTRATION_LIMIT,
        ge=0,
        le=1,
        description="Max single-name weight as fraction of household NAV",
    )
    liquidity_tier_min_pct: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Min NAV share in liquidity tiers 1+2 when set",
    )
    turnover_budget_pct: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Annual turnover budget as fraction of NAV when set",
    )
