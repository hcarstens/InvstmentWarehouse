"""Reporting plane — household performance panel data."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from warehouse.infra.db.base import session_scope
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.reporting.performance import (
    HouseholdPerformanceReport,
    build_household_performance_report,
)


class ReportingPerformanceData(BaseModel):
    household_id: str
    report: HouseholdPerformanceReport | None
    error: str | None = None


def load_reporting_performance(
    *,
    household_id: str = DEMO_HOUSEHOLD_ID,
    as_of: date | None = None,
) -> ReportingPerformanceData:
    """Load household performance snapshot for the reporting dashboard."""
    effective_as_of = as_of or date(2026, 6, 24)
    try:
        with session_scope() as session:
            report = build_household_performance_report(
                session,
                household_id=household_id,
                as_of=effective_as_of,
            )
        return ReportingPerformanceData(
            household_id=household_id,
            report=report,
        )
    except Exception as exc:
        return ReportingPerformanceData(
            household_id=household_id,
            report=None,
            error=str(exc),
        )
