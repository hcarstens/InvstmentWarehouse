"""Risk API service — pure evaluate_risk entry point (contract v0)."""

from __future__ import annotations

from warehouse.research.risk.engine import evaluate_portfolio_risk
from warehouse.research.risk.models import (
    AssetPortfolio,
    PortfolioRiskReport,
    RiskRequest,
    RiskResult,
    ScenarioSet,
)
from warehouse.research.risk.scenarios import assumptions_for


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


def evaluate_risk(request: RiskRequest, manifest: AssetPortfolio) -> RiskResult:
    """Evaluate portfolio risk for a manifest and request."""
    base = assumptions_for("base")
    report = evaluate_portfolio_risk(
        manifest,
        request.horizon,
        notional_usd=request.notional_usd,
        assumptions=base,
    )
    scenarios: dict[str, PortfolioRiskReport] = {}
    for regime in _scenario_regimes(request.run_scenarios):
        alt = assumptions_for(regime)
        scenarios[regime] = evaluate_portfolio_risk(
            manifest,
            request.horizon,
            notional_usd=request.notional_usd,
            assumptions=alt,
        )
    return RiskResult(report=report, scenarios=scenarios, deltas=None)
