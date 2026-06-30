"""Collect plane outputs into a frozen ReportBundle."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from warehouse.config import get_settings
from warehouse.data.alternatives.service import (
    AlternativeHoldingView,
    list_alternative_holdings,
)
from warehouse.data.ledger.views import LotPositionView, list_lot_positions
from warehouse.decision.analyst.attribution import (
    AttributionError,
    evaluate_attribution,
)
from warehouse.decision.analyst.models import AttributionReport
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
from warehouse.research.risk.adapters.ledger import HouseholdRiskManifest
from warehouse.research.risk.models import (
    RiskHorizon,
    RiskRequest,
    RiskResult,
    ScenarioSet,
)
from warehouse.research.risk.portfolio_builder import (
    build_portfolio_from_holdings,
)
from warehouse.research.risk.scenarios import assumptions_for
from warehouse.research.risk.service import evaluate_risk

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
    "decision.analyst:evaluate_attribution",
    "research.risk:evaluate_risk",
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


def _household_notional(
    positions: list[LotPositionView],
    alt_holdings: list[AlternativeHoldingView],
) -> Decimal:
    lot_nav = sum(
        (p.market_value for p in positions if p.market_value is not None),
        Decimal("0"),
    )
    alt_nav = sum((a.current_nav for a in alt_holdings), Decimal("0"))
    return lot_nav + alt_nav


def _build_household_manifest_from_session(
    session: Session,
    household_id: str,
) -> HouseholdRiskManifest:
    """Session-backed manifest for risk evaluation (walk-forward safe)."""
    positions = list_lot_positions(session, household_id=household_id)
    alts = list_alternative_holdings(session, household_id=household_id)
    portfolio = build_portfolio_from_holdings(household_id, positions, alts)
    portfolio = portfolio.model_copy(update={"source": "ledger"})
    notional = _household_notional(positions, alts)
    return HouseholdRiskManifest(
        portfolio=portfolio,
        notional_usd=notional if notional > 0 else None,
    )


def _collect_attribution(
    positions: list[LotPositionView],
    *,
    household_id: str,
    as_of: date,
) -> AttributionReport | None:
    attributable = [
        p
        for p in positions
        if p.market_value is not None and p.market_value > 0
    ]
    if not attributable:
        return None

    settings = get_settings()
    try:
        return evaluate_attribution(
            attributable,
            assumptions_for("base").class_expected_return,
            household_id=household_id,
            as_of=as_of,
            config_version=settings.analyst_config_version,
            min_holding_years=Decimal(str(settings.analyst_min_holding_years)),
        )
    except AttributionError as err:
        raise ReportWriterError(
            f"Attribution failed for household {household_id} "
            f"as_of={as_of.isoformat()}: {err}"
        ) from err


def _collect_risk_headline(
    session: Session,
    household_id: str,
) -> RiskResult:
    settings = get_settings()
    horizon = RiskHorizon.parse(settings.risk_dashboard_horizon_years)
    try:
        manifest = _build_household_manifest_from_session(
            session, household_id
        )
        request = RiskRequest(
            horizon=horizon,
            notional_usd=manifest.notional_usd,
            run_scenarios=ScenarioSet.NONE,
        )
        return evaluate_risk(request, manifest.portfolio)
    except (ValueError, TypeError) as err:
        raise ReportWriterError(
            f"Risk headline failed for household {household_id}: {err}"
        ) from err


def _build_limitations(
    *,
    snapshot_id: str,
    as_of_date: date,
    tax_scenarios: tuple[ReportingTaxResult, ...],
    open_breaks: tuple[ReconciliationBreak, ...],
    pending_approval_count: int,
    attribution_limitations: tuple[str, ...] = (),
    risk_limitations: tuple[str, ...] = (),
    attribution_skipped: bool = False,
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
    if attribution_skipped:
        items.append("Attribution not computed — no attributable positions.")
    items.extend(attribution_limitations)
    items.extend(risk_limitations)
    return tuple(items)


def _risk_limitation_notes(risk: RiskResult) -> tuple[str, ...]:
    meta = risk.report.manifest
    notes: list[str] = [
        (
            f"Risk headline uses assumption_regime={meta.assumption_regime}, "
            f"mark_source={meta.mark_source}, vol_window_days="
            f"{meta.vol_window_days}."
        ),
    ]
    if meta.mark_source != "live":
        notes.append("Risk metrics use model priors — not custodian marks.")
    return tuple(notes)


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

    attribution = _collect_attribution(
        positions,
        household_id=household_id,
        as_of=as_of,
    )
    risk_headline = _collect_risk_headline(session, household_id)

    attribution_lims = (
        tuple(attribution.limitations) if attribution is not None else ()
    )
    risk_lims = _risk_limitation_notes(risk_headline)

    limitations = _build_limitations(
        snapshot_id=snapshot_id,
        as_of_date=as_of,
        tax_scenarios=tax_scenarios,
        open_breaks=open_breaks,
        pending_approval_count=pending_count,
        attribution_limitations=attribution_lims,
        risk_limitations=risk_lims,
        attribution_skipped=attribution is None,
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
        attribution=attribution,
        risk_headline=risk_headline,
    )
