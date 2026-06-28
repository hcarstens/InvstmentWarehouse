"""Tax-aware optimizer v0 — TLH heuristics + greedy rebalance.

Upgrade path: full MIP (Gurobi / CPLEX) for lot-discrete problems.
Every output includes rationale: lots, binding constraints, tax delta
vs baseline.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from warehouse.decision.optimizer.models import RebalanceProposal


class TradeProposal(BaseModel):
    lot_id: str | None = None
    security_id: str
    account_id: str
    side: str  # buy | sell
    quantity: Decimal
    rationale: str


class OptimizationResult(BaseModel):
    """v0 TLH ``trades`` + breach flags, plus the additive po0 ``rebalance``.

    Audit/replay-critical → frozen (§4). ``rebalance`` is the advisory
    constrained-MV leg (w*/Δw/RC); the QP path never appends to ``trades``
    (§B.1). Because the model is frozen, callers set ``rebalance`` at
    construction or via ``model_copy(update=...)`` — never post-hoc assignment.
    """

    model_config = ConfigDict(frozen=True)

    household_id: str
    config_version: str
    trades: list[TradeProposal]
    estimated_tax_delta: Decimal
    binding_constraints: list[str] = Field(default_factory=list)
    rebalance: RebalanceProposal | None = None
