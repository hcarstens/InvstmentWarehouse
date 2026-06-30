"""Per-op request/result bodies for the messaging catalog (contract §5).

Composition layer — may import plane *types* (unlike ``core.py``). Result
wrappers exist because the dispatch boundary returns ``BaseModel``, while some
backing functions return bare ``list``/``tuple``.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.analyst import AttributionReport
from warehouse.decision.approval import ApprovalStatus
from warehouse.decision.ips import InvestmentPolicyStatement
from warehouse.decision.ips.monitor import IpsDriftReport
from warehouse.decision.optimizer import OptimizationResult
from warehouse.decision.tax.scenarios import (
    TaxScenarioOverlays,
    TaxScenarioResult,
)
from warehouse.execution.oms.service import StagedOrderView
from warehouse.execution.reconciliation.service import ReconciliationBreak
from warehouse.research.risk.models import (
    AssetPortfolio,
    RiskRequest,
    RiskResult,
)

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
    """Open an approval gate — exactly one subject (optimization XOR report).

    rw6: report-document approvals reuse ``approval.create`` (messaging S1 — no
    second op) by passing ``report_snapshot_id`` instead of
    ``optimization_run_id``. Supplying both or neither raises (the gate is the
    declaration, §8).
    """

    household_id: str
    optimization_run_id: str | None = None
    report_snapshot_id: str | None = None

    @model_validator(mode="after")
    def _exactly_one_subject(self) -> ApprovalCreatePayload:
        has_opt = self.optimization_run_id is not None
        has_report = self.report_snapshot_id is not None
        if has_opt == has_report:
            raise ValueError(
                "approval.create requires exactly one of "
                "optimization_run_id or report_snapshot_id"
            )
        return self


class ApprovalDecidePayload(BaseModel):
    request_id: str
    status: ApprovalStatus
    reviewer_id: str


class OrdersStagePayload(BaseModel):
    approval_request_id: str


class TaxScenarioPayload(BaseModel):
    positions: list[LotPositionView]
    overlays: TaxScenarioOverlays = TaxScenarioOverlays()


class AttributionEvaluatePayload(BaseModel):
    """Portfolio-Analyst attribution leg — per-position decomposition."""

    household_id: str
    positions: list[LotPositionView]
    as_of_date: date | None = None


class PmAdvisePayload(BaseModel):
    """Portfolio-Manager working set — the (P, IPS) artifact, sliced per op."""

    household_id: str
    positions: list[LotPositionView]
    ips: InvestmentPolicyStatement
    manifest: AssetPortfolio
    request: RiskRequest
    tax_overlays: TaxScenarioOverlays = TaxScenarioOverlays()
    cohort_id: str | None = None
    as_of_date: date | None = None


class ReportBuildPayload(BaseModel):
    household_id: str
    period_label: str | None = None
    as_of_date: date | None = None


class AxiomScore(StrEnum):
    PASS = "pass"
    WARN = "warn"
    BREACH = "breach"
    NOT_COMPUTED = "not_computed"


class PmNarrative(BaseModel):
    """7-axiom ℍ_Allocation diagnostic — audit snapshot."""

    model_config = ConfigDict(frozen=True)

    correlation_id: str
    axioms_scored: dict[str, AxiomScore]
    headline: str
    specialist_status: dict[str, str]


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


class AdviceBundle(BaseModel):
    """Portfolio-Manager advisory output — mutates nothing (§4.1)."""

    model_config = ConfigDict(frozen=True)

    risk: RiskResult
    proposal: OptimizationResult
    tax: TaxScenarioResult
    drift: IpsDriftReport
    attribution: AttributionReport | None = None
    narrative: PmNarrative | None = None
