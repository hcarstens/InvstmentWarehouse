"""Tax-aware optimizer v0 — TLH heuristics + greedy rebalance.

Upgrade path: full MIP (Gurobi / CPLEX) for lot-discrete problems.
Every output includes rationale: lots, binding constraints, tax delta vs baseline.
"""

from decimal import Decimal

from pydantic import BaseModel, Field


class TradeProposal(BaseModel):
    lot_id: str | None = None
    security_id: str
    account_id: str
    side: str  # buy | sell
    quantity: Decimal
    rationale: str


class OptimizationResult(BaseModel):
    household_id: str
    config_version: str
    trades: list[TradeProposal]
    estimated_tax_delta: Decimal
    binding_constraints: list[str] = Field(default_factory=list)
