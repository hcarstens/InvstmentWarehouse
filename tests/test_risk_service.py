"""Risk service — evaluate_risk contract v0a tests."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from warehouse.research.risk.engine import evaluate_portfolio_risk
from warehouse.research.risk.models import (
    AssetPortfolio,
    RiskHorizon,
    RiskRequest,
    ScenarioSet,
)
from warehouse.research.risk.service import evaluate_risk

FIXTURE = Path(__file__).parent / "fixtures" / "sample_portfolio.json"


def _sample_portfolio() -> AssetPortfolio:
    body = json.loads(FIXTURE.read_text())
    return AssetPortfolio.model_validate(body["asset_portfolio"])


def test_evaluate_risk_matches_engine() -> None:
    portfolio = _sample_portfolio()
    horizon = RiskHorizon.parse("5y")
    notional = Decimal("1000000")
    request = RiskRequest(
        horizon=horizon,
        notional_usd=notional,
        run_scenarios=ScenarioSet.NONE,
    )
    direct = evaluate_portfolio_risk(portfolio, horizon, notional_usd=notional)
    result = evaluate_risk(request, portfolio)
    assert result.deltas is None
    assert result.scenarios == {}
    assert result.report.input_fingerprint == direct.input_fingerprint
    assert (
        result.report.level_1_portfolio.parametric_var.value
        == direct.level_1_portfolio.parametric_var.value
    )


def test_asset_portfolio_provenance_defaults() -> None:
    portfolio = _sample_portfolio()
    assert portfolio.source == "synthetic"
    assert portfolio.complexity is None
