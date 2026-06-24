"""IPS monitoring — drift vs strategic allocation and policy constraints."""

from decimal import Decimal

from pydantic import BaseModel, Field


class AllocationTarget(BaseModel):
    asset_class: str
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
