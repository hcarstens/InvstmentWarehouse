"""Per-op request/result bodies for the messaging catalog (contract §5).

Composition layer — may import plane *types* (unlike ``core.py``). Result
wrappers exist because the dispatch boundary returns ``BaseModel``, while some
backing functions return bare ``list``/``tuple``.
"""

from __future__ import annotations

from pydantic import BaseModel

from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.approval import ApprovalStatus
from warehouse.decision.ips import InvestmentPolicyStatement
from warehouse.decision.optimizer import OptimizationResult
from warehouse.execution.oms.service import StagedOrderView
from warehouse.execution.reconciliation.service import ReconciliationBreak
from warehouse.research.risk.models import AssetPortfolio, RiskRequest

# --- request payloads -------------------------------------------------------


class LedgerPositionsPayload(BaseModel):
    household_id: str


class RiskEvaluatePayload(BaseModel):
    request: RiskRequest
    manifest: AssetPortfolio


class PolicyCheckPayload(BaseModel):
    household_id: str
    positions: list[LotPositionView]
    ips: InvestmentPolicyStatement


class OptimizePayload(BaseModel):
    household_id: str
    positions: list[LotPositionView]
    ips: InvestmentPolicyStatement


class TradeValidatePayload(BaseModel):
    lot: LotPositionView
    ips: InvestmentPolicyStatement


class IngestRunPayload(BaseModel):
    household_id: str
    custodian_id: str
    path: str


class ReconcilePayload(BaseModel):
    household_id: str
    ingest_run_id: str


class OptimizerPersistPayload(BaseModel):
    result: OptimizationResult
    input_snapshot_id: str = "snapshot_local"


class ApprovalCreatePayload(BaseModel):
    optimization_run_id: str
    household_id: str


class ApprovalDecidePayload(BaseModel):
    request_id: str
    status: ApprovalStatus
    reviewer_id: str


class OrdersStagePayload(BaseModel):
    approval_request_id: str


# --- result wrappers (boundary returns must be BaseModel) -------------------


class PositionSet(BaseModel):
    positions: list[LotPositionView]


class TradeValidation(BaseModel):
    allowed: bool
    binding: list[str]


class ReconcileResult(BaseModel):
    breaks: list[ReconciliationBreak]


class StagedOrders(BaseModel):
    orders: list[StagedOrderView]
