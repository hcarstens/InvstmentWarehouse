"""Risk API — parse requests and evaluate portfolio risk manifest."""

from __future__ import annotations

import json
from decimal import Decimal
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
    notional_raw = body.get("notional_usd")
    notional = Decimal(str(notional_raw)) if notional_raw is not None else None

    report = evaluate_portfolio_risk(portfolio, horizon, notional_usd=notional)

    settings = get_settings()
    level_1 = report.level_1_portfolio
    log_fields = {
        "horizon_years": str(horizon.years),
        "fingerprint": report.input_fingerprint,
        "annualized_vol": str(level_1.annualized_volatility.value),
        "parametric_var": str(level_1.parametric_var.value),
        "model_version": report.model_version,
    }
    if settings.risk_log_inputs:
        logger.info(
            "risk_evaluated",
            portfolio_id=portfolio.portfolio_id,
            notional_usd=str(notional) if notional else None,
            **log_fields,
        )
    else:
        logger.info("risk_evaluated", **log_fields)

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
        "reference": [
            "docs/research/risk_units_measures.md",
            "docs/research/portfolio_risk.md",
            "docs/research/simple_risk_models.md",
        ],
        "request": {
            "asset_portfolio": {
                "portfolio_id": "optional string",
                "allocations": [
                    {
                        "asset_class": "equity|fixed_income|commodities|fx|alternatives|cash",
                        "weight": "0.0-1.0, must sum to 1",
                        "duration_years": "optional — fixed income / alts",
                        "beta": "optional — equity sleeve",
                        "liquidity_tier": "1=liquid, 2=semi, 3=illiquid",
                        "measurement": "measurable|fermi|auto",
                    }
                ],
            },
            "horizon": "e.g. 5y or 5 — investment horizon in years",
            "notional_usd": "optional — enables Level 1 dollar VaR/ES and Level 4 dollar P&L",
        },
        "response": {
            "level_1_portfolio": "sigma, parametric VaR/ES with (alpha, h) metadata",
            "level_2_contributions": "pct_variance by class and duration bucket",
            "level_3_sensitivities": "native units (beta, duration, fermi)",
            "level_4_stress": "named replay 2008/2020/2022",
            "liquidity": "liquidity-time days by tier",
            "measurement_summary": "measurable vs fermi weight and risk share",
        },
        "privacy": (
            "Allocations and horizons are fingerprinted; raw inputs are not logged "
            "when risk_log_inputs=false"
        ),
    }
