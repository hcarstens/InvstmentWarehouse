"""Risk API service — pure evaluate_risk entry point (contract v0)."""

from __future__ import annotations

from warehouse.research.risk.engine import evaluate_portfolio_risk
from warehouse.research.risk.models import (
    AssetPortfolio,
    RiskRequest,
    RiskResult,
)


def evaluate_risk(request: RiskRequest, manifest: AssetPortfolio) -> RiskResult:
    """Evaluate portfolio risk for a manifest and request.

    v0a: wraps ``evaluate_portfolio_risk``; ``run_scenarios`` and ``deltas`` land in v0b/v1.
    """
    report = evaluate_portfolio_risk(
        manifest,
        request.horizon,
        notional_usd=request.notional_usd,
    )
    return RiskResult(report=report, scenarios={}, deltas=None)
