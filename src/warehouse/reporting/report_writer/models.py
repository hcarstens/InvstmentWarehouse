"""Frozen report-writer terrain-map types."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from warehouse.decision.ips.monitor import IpsDriftReport
from warehouse.execution.oms.service import StagedOrderView
from warehouse.execution.reconciliation.service import ReconciliationBreak
from warehouse.reporting.performance import HouseholdPerformanceReport
from warehouse.reporting.tax import ReportingTaxResult


class ReportAudience(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class ReportPeriod(BaseModel):
    """Reporting window — directory key and optional bounds."""

    model_config = ConfigDict(frozen=True)

    label: str
    start_date: date | None = None
    end_date: date | None = None

    @classmethod
    def month_end(cls, as_of: date) -> ReportPeriod:
        return cls(
            label=f"month-end-{as_of.isoformat()}",
            end_date=as_of,
        )


class ReportBundle(BaseModel):
    """Frozen terrain map — compiled facts from plane outputs."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    household_id: str
    period: ReportPeriod
    as_of_date: date
    generated_at: datetime
    performance: HouseholdPerformanceReport | None
    ips_drift: IpsDriftReport | None
    tax_scenarios: tuple[ReportingTaxResult, ...]
    staged_orders: tuple[StagedOrderView, ...]
    pending_approval_count: int
    open_breaks: tuple[ReconciliationBreak, ...]
    limitations: tuple[str, ...]
    data_sources: tuple[str, ...]


class WrittenHouseholdReport(BaseModel):
    """Frozen write result — paths to rendered report artifacts."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    household_id: str
    period_label: str
    as_of_date: date
    generated_at: datetime
    output_dir: str
    internal_markdown_path: str
    external_markdown_path: str
    bundle_json_path: str
    external_pdf_path: str | None = None
    external_pdf_sha256: str | None = None
