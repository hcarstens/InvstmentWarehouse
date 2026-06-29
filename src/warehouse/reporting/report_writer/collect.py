"""Collect plane outputs into a frozen ReportBundle."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.approval import ApprovalStatus
from warehouse.decision.approval.service import list_approval_requests
from warehouse.decision.ips.monitor import build_ips_drift_report
from warehouse.decision.ips.store import load_ips
from warehouse.decision.tax.scenarios import TaxScenarioOverlays
from warehouse.execution.oms.service import list_staged_orders
from warehouse.execution.reconciliation.service import (
    ReconciliationBreak,
    list_reconciliation_breaks,
)
from warehouse.reporting.performance import (
    build_household_performance_report,
)
from warehouse.reporting.report_writer.models import (
    ReportBundle,
    ReportPeriod,
)
from warehouse.reporting.tax import (
    ReportingTaxResult,
    run_reporting_tax_scenario,
)

_DEFAULT_TAX_SCENARIOS: tuple[tuple[str, TaxScenarioOverlays], ...] = (
    ("baseline", TaxScenarioOverlays(apply_niit=False)),
    ("niit_overlay", TaxScenarioOverlays(apply_niit=True)),
)

_DATA_SOURCES: tuple[str, ...] = (
    "reporting.performance:build_household_performance_report",
    "decision.ips:build_ips_drift_report",
    "reporting.tax:run_reporting_tax_scenario",
    "execution.oms:list_staged_orders",
    "execution.recon:list_reconciliation_breaks",
    "decision.approval:list_approval_requests",
)


class ReportWriterError(ValueError):
    """Report bundle collection failed — missing preconditions."""


def _pending_approval_count(session: Session, household_id: str) -> int:
    requests = list_approval_requests(
        session,
        household_id=household_id,
        limit=500,
    )
    return sum(
        1 for req in requests if req.status == ApprovalStatus.PENDING.value
    )


def _collect_tax_scenarios(
    session: Session,
    household_id: str,
    *,
    as_of: date,
) -> tuple[ReportingTaxResult, ...]:
    results: list[ReportingTaxResult] = []
    for scenario_name, overlays in _DEFAULT_TAX_SCENARIOS:
        results.append(
            run_reporting_tax_scenario(
                session,
                household_id,
                scenario_name=scenario_name,
                overlays=overlays,
                as_of=as_of,
            )
        )
    return tuple(results)


def _build_limitations(
    *,
    snapshot_id: str,
    as_of_date: date,
    tax_scenarios: tuple[ReportingTaxResult, ...],
    open_breaks: tuple[ReconciliationBreak, ...],
    pending_approval_count: int,
) -> tuple[str, ...]:
    items: list[str] = [
        (
            f"Data vintage = {as_of_date.isoformat()}; "
            f"snapshot = {snapshot_id}."
        ),
    ]
    if tax_scenarios and all(
        ts.tax_delta == Decimal("0") for ts in tax_scenarios
    ):
        items.append(
            "Tax scenario deltas are zero-stubbed — not for client filing."
        )
    if open_breaks:
        items.append(
            "Open reconciliation breaks — exhibits may not match "
            "custodian statements."
        )
        items.append(
            "Reconciliation breaks listed are firm-wide, not household-scoped."
        )
    if pending_approval_count > 0:
        items.append(
            "Pending approvals — figures subject to change before delivery."
        )
    return tuple(items)


def collect_report_bundle(
    session: Session,
    household_id: str,
    *,
    period: ReportPeriod,
    as_of: date,
) -> ReportBundle:
    """Assemble a frozen terrain map from registered plane outputs."""
    positions = list_lot_positions(session, household_id=household_id)
    if not positions:
        raise ReportWriterError(f"No positions for household {household_id}")
    ips = load_ips(session, household_id)
    if ips is None:
        raise ReportWriterError(f"No IPS found for household {household_id}")

    performance = build_household_performance_report(
        session,
        household_id=household_id,
        as_of=as_of,
    )
    ips_drift = build_ips_drift_report(
        session,
        household_id,
        positions,
        ips,
    )
    tax_scenarios = _collect_tax_scenarios(
        session,
        household_id,
        as_of=as_of,
    )
    staged_orders = tuple(
        list_staged_orders(session, household_id=household_id)
    )
    open_breaks = tuple(list_reconciliation_breaks(session, open_only=True))
    pending_count = _pending_approval_count(session, household_id)
    snapshot_id = f"rpt_{uuid4().hex[:12]}"
    generated_at = datetime.now(UTC)

    limitations = _build_limitations(
        snapshot_id=snapshot_id,
        as_of_date=as_of,
        tax_scenarios=tax_scenarios,
        open_breaks=open_breaks,
        pending_approval_count=pending_count,
    )

    return ReportBundle(
        snapshot_id=snapshot_id,
        household_id=household_id,
        period=period,
        as_of_date=as_of,
        generated_at=generated_at,
        performance=performance,
        ips_drift=ips_drift,
        tax_scenarios=tax_scenarios,
        staged_orders=staged_orders,
        pending_approval_count=pending_count,
        open_breaks=open_breaks,
        limitations=limitations,
        data_sources=_DATA_SOURCES,
    )
