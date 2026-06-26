"""Risk API service — pure evaluate_risk entry point (contract v0/v1)."""

from __future__ import annotations

from warehouse.research.risk.assumptions import RiskAssumptions
from warehouse.research.risk.engine import evaluate_portfolio_risk
from warehouse.research.risk.models import (
    AssetPortfolio,
    PortfolioRiskReport,
    RiskDeltas,
    RiskRequest,
    RiskResult,
    ScenarioSet,
)
from warehouse.research.risk.overlay import apply_overlay, diff_reports
from warehouse.research.risk.scenarios import (
    assumptions_for,
    validate_correlation_psd,
)


def _scenario_regimes(run_scenarios: ScenarioSet) -> tuple[str, ...]:
    if run_scenarios == ScenarioSet.NONE:
        return ()
    if run_scenarios == ScenarioSet.HIGH_RISK:
        return ("high_risk",)
    if run_scenarios == ScenarioSet.LOW_RISK:
        return ("low_risk",)
    if run_scenarios == ScenarioSet.ALL:
        return ("high_risk", "low_risk")
    return ()


def _resolve_assumptions(
    assumptions: RiskAssumptions | None,
) -> RiskAssumptions:
    if assumptions is None:
        return assumptions_for("base")
    if assumptions.regime not in ("base", "high_risk", "low_risk"):
        validate_correlation_psd(assumptions)
    return assumptions


def _evaluate_report(
    manifest: AssetPortfolio,
    request: RiskRequest,
    assumptions: RiskAssumptions,
    *,
    stress_filter: str | None = None,
) -> PortfolioRiskReport:
    return evaluate_portfolio_risk(
        manifest,
        request.horizon,
        notional_usd=request.notional_usd,
        assumptions=assumptions,
        stress_filter=stress_filter,
    )


def _evaluate_deltas(
    baseline: PortfolioRiskReport,
    request: RiskRequest,
    manifest: AssetPortfolio,
    assumptions: RiskAssumptions,
) -> RiskDeltas:
    overlay = request.overlay
    assert overlay is not None
    derived = apply_overlay(manifest, overlay)
    proposed = _evaluate_report(
        derived,
        request,
        assumptions,
        stress_filter=overlay.stress_pack,
    )
    return diff_reports(
        baseline,
        proposed,
        overlay_label=overlay.label,
    )


def evaluate_risk(
    request: RiskRequest,
    manifest: AssetPortfolio,
    *,
    assumptions: RiskAssumptions | None = None,
) -> RiskResult:
    """Evaluate portfolio risk; optional overlay produces ``RiskDeltas``."""
    priors = _resolve_assumptions(assumptions)
    report = _evaluate_report(manifest, request, priors)

    scenarios: dict[str, PortfolioRiskReport] = {}
    for regime in _scenario_regimes(request.run_scenarios):
        alt = assumptions_for(regime)
        scenarios[regime] = _evaluate_report(manifest, request, alt)

    deltas = None
    if request.overlay is not None:
        deltas = _evaluate_deltas(report, request, manifest, priors)

    return RiskResult(report=report, scenarios=scenarios, deltas=deltas)
