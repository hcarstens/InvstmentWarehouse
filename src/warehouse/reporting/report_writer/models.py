"""Frozen report-writer terrain-map types."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from warehouse.decision.analyst.models import AttributionReport
from warehouse.decision.ips.monitor import IpsDriftReport
from warehouse.execution.oms.service import StagedOrderView
from warehouse.execution.reconciliation.service import ReconciliationBreak
from warehouse.reporting.performance import HouseholdPerformanceReport
from warehouse.reporting.tax import ReportingTaxResult
from warehouse.research.risk.models import RiskResult


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


class ComparisonDelta(BaseModel):
    """One figure placed against its prior-period value (persona Fi2).

    ``abs_delta``/``pct_delta`` are ``None`` when either side is absent — the
    renderer shows ``n/a`` rather than fabricating a zero (honesty rule §3).
    ``pct_delta`` is a fraction (``0.05`` == +5%); ``None`` when prior is zero.
    """

    model_config = ConfigDict(frozen=True)

    label: str
    current: Decimal | None
    prior: Decimal | None
    abs_delta: Decimal | None
    pct_delta: Decimal | None


class ReportComparison(BaseModel):
    """Prior-period reference + per-figure deltas for the current bundle.

    Sourced from the most recent prior ``bundle.json`` for the household whose
    ``as_of`` is strictly earlier (walk-forward safe — no lookahead). A
    lightweight delta snapshot, not a nested ``ReportBundle``, so the chain
    never recurses.
    """

    model_config = ConfigDict(frozen=True)

    prior_snapshot_id: str
    prior_as_of_date: date
    is_adjacent: bool
    performance: tuple[ComparisonDelta, ...]
    drift: tuple[ComparisonDelta, ...]


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
    attribution: AttributionReport | None = None
    risk_headline: RiskResult | None = None
    comparison: ReportComparison | None = None


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
