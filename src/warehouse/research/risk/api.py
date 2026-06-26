"""Risk API — parse requests and evaluate portfolio risk manifest."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from warehouse.research.risk.models import (
    AssetPortfolio,
    RiskHorizon,
    RiskRequest,
    ScenarioSet,
)
from warehouse.research.risk.observability import (
    log_risk_evaluated,
    record_risk_failure,
)
from warehouse.research.risk.service import evaluate_risk


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

    request = RiskRequest(
        horizon=horizon,
        notional_usd=notional,
        run_scenarios=ScenarioSet.NONE,
    )
    result = evaluate_risk(request, portfolio)
    log_risk_evaluated(
        result,
        request=request,
        manifest=portfolio,
        surface="api",
    )
    return result.report.model_dump(mode="json")


def evaluate_risk_json(raw: str | bytes) -> tuple[int, str]:
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as err:
        record_risk_failure(err, surface="http", http_status=400)
        return 400, json.dumps({"error": f"Invalid JSON: {err}"})
    if not isinstance(body, dict):
        api_err = RiskApiError("Request body must be a JSON object")
        record_risk_failure(api_err, surface="http", http_status=400)
        return 400, json.dumps({"error": str(api_err)})
    try:
        result = evaluate_risk_request(body)
        return 200, json.dumps(result, indent=2)
    except RiskApiError as err:
        record_risk_failure(err, surface="http", http_status=400)
        return 400, json.dumps({"error": str(err)})
    except ValueError as err:
        record_risk_failure(err, surface="http", http_status=422)
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
        "notifications": {
            "risk_notify_on_error": "master switch for failure alerts",
            "risk_notify_email_enabled": "send SMTP email when true",
            "risk_notify_email_to": "comma-separated recipients",
            "risk_notify_email_from": "From header",
            "risk_notify_smtp_host": "SMTP host (required to send email)",
            "risk_notify_smtp_port": "SMTP port (default 587)",
            "risk_notify_messaging_enabled": "POST JSON webhook when true",
            "risk_notify_messaging_webhook_url": "Slack or generic webhook URL",
            "risk_notify_messaging_channel": "channel label included in payload",
        },
    }
