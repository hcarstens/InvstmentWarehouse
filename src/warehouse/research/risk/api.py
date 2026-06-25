"""Risk API — parse requests and evaluate portfolio risk."""

from __future__ import annotations

import json
from typing import Any

import structlog

from warehouse.config import get_settings
from warehouse.research.risk.engine import evaluate_portfolio_risk
from warehouse.research.risk.models import AssetPortfolio, RiskHorizon

logger = structlog.get_logger(__name__)


class RiskApiError(ValueError):
    """Invalid risk API request."""


def evaluate_risk_request(body: dict[str, Any]) -> dict[str, Any]:
    if "asset_portfolio" not in body:
        raise RiskApiError("Missing required field: asset_portfolio")
    if "horizon" not in body:
        raise RiskApiError("Missing required field: horizon")

    portfolio = AssetPortfolio.model_validate(body["asset_portfolio"])
    horizon = RiskHorizon.parse(body["horizon"])
    report = evaluate_portfolio_risk(portfolio, horizon)

    settings = get_settings()
    if settings.risk_log_inputs:
        logger.info(
            "risk_evaluated",
            portfolio_id=portfolio.portfolio_id,
            horizon_years=str(horizon.years),
            fingerprint=report.input_fingerprint,
            total_risk=str(report.total_risk),
        )
    else:
        logger.info(
            "risk_evaluated",
            horizon_years=str(horizon.years),
            fingerprint=report.input_fingerprint,
            total_risk=str(report.total_risk),
            model_version=report.model_version,
        )

    return report.model_dump(mode="json")


def evaluate_risk_json(raw: str | bytes) -> tuple[int, str]:
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as err:
        return 400, json.dumps({"error": f"Invalid JSON: {err}"})
    if not isinstance(body, dict):
        return 400, json.dumps({"error": "Request body must be a JSON object"})
    try:
        result = evaluate_risk_request(body)
        return 200, json.dumps(result, indent=2)
    except RiskApiError as err:
        return 400, json.dumps({"error": str(err)})
    except ValueError as err:
        return 422, json.dumps({"error": str(err)})


def risk_api_schema() -> dict[str, Any]:
    return {
        "endpoint": "/api/risk",
        "method": "POST",
        "request": {
            "asset_portfolio": {
                "portfolio_id": "optional string",
                "allocations": [
                    {
                        "asset_class": "equity|fixed_income|commodities|fx|alternatives|cash",
                        "weight": "0.0-1.0, must sum to 1",
                        "duration_years": "optional, for fixed income / alts",
                        "liquidity_tier": "1=liquid, 2=semi, 3=illiquid",
                        "measurement": "measurable|fermi|auto",
                    }
                ],
            },
            "horizon": "e.g. 5y or 5 — investment horizon in years",
        },
        "response": "PortfolioRiskReport JSON with by_class, by_duration, measurement_summary",
        "privacy": (
            "Allocations are fingerprinted; raw inputs are not logged when risk_log_inputs=false"
        ),
    }
