"""Risk API and evaluation engine tests."""

from __future__ import annotations

import json
import threading
from decimal import Decimal
from http.server import HTTPServer
from pathlib import Path

import pytest

from warehouse.dashboard.server import DashboardHandler
from warehouse.research.risk.api import (
    RiskApiError,
    evaluate_risk_json,
    evaluate_risk_request,
    risk_api_schema,
)
from warehouse.research.risk.by_class import aggregate_class_risk, evaluate_class_risk
from warehouse.research.risk.by_duration import evaluate_duration_risk
from warehouse.research.risk.engine import evaluate_portfolio_risk
from warehouse.research.risk.fingerprint import portfolio_fingerprint
from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    AssetPortfolio,
    MeasurementMode,
    RiskHorizon,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_portfolio.json"


def _sample_request() -> dict:
    return json.loads(FIXTURE.read_text())


def test_risk_api_schema() -> None:
    schema = risk_api_schema()
    assert schema["endpoint"] == "/api/risk"
    assert schema["method"] == "POST"
    assert "privacy" in schema


def test_evaluate_risk_request_returns_report() -> None:
    result = evaluate_risk_request(_sample_request())
    assert result["portfolio_id"] == "demo"
    assert float(result["horizon_years"]) == 5
    assert result["model_version"] == "2026.01"
    assert len(result["input_fingerprint"]) == 16
    assert len(result["by_class"]) == 3
    assert len(result["by_duration"]) >= 2
    assert float(result["total_risk"]) > 0
    assert float(result["confidence_low"]) <= float(result["total_risk"]) <= float(
        result["confidence_high"]
    )


def test_evaluate_risk_json_invalid_body() -> None:
    status, body = evaluate_risk_json("{not json")
    assert status == 400
    assert "Invalid JSON" in json.loads(body)["error"]


def test_evaluate_risk_json_missing_fields() -> None:
    status, body = evaluate_risk_json(json.dumps({"horizon": "5y"}))
    assert status == 400
    assert "asset_portfolio" in json.loads(body)["error"]


def test_weights_must_sum_to_one() -> None:
    body = _sample_request()
    body["asset_portfolio"]["allocations"][0]["weight"] = 0.9
    status, payload = evaluate_risk_json(json.dumps(body))
    assert status == 422


def test_class_risk_measurable_vs_fermi() -> None:
    horizon = RiskHorizon.parse("5y")
    equity = evaluate_class_risk(
        AllocationSlot(asset_class=AssetClass.EQUITY, weight=Decimal("0.5")),
        horizon,
    )
    alt = evaluate_class_risk(
        AllocationSlot(
            asset_class=AssetClass.ALTERNATIVES,
            weight=Decimal("0.5"),
            liquidity_tier=3,
        ),
        horizon,
    )
    assert equity.measurement == MeasurementMode.MEASURABLE
    assert alt.measurement == MeasurementMode.FERMI
    assert alt.annual_volatility > equity.annual_volatility


def test_duration_buckets_and_mismatch() -> None:
    horizon = RiskHorizon.parse("5y")
    portfolio = AssetPortfolio.model_validate(_sample_request()["asset_portfolio"])
    by_class = [evaluate_class_risk(slot, horizon) for slot in portfolio.allocations]
    by_duration = evaluate_duration_risk(portfolio.allocations, horizon, by_class)
    buckets = {row.bucket for row in by_duration}
    assert "medium" in buckets
    medium = next(row for row in by_duration if row.bucket == "medium")
    assert float(medium.horizon_mismatch) == pytest.approx(0.35, rel=1e-3)


def test_fingerprint_stable_for_same_inputs() -> None:
    portfolio = AssetPortfolio.model_validate(_sample_request()["asset_portfolio"])
    horizon = RiskHorizon.parse("5y")
    assert portfolio_fingerprint(portfolio, horizon) == portfolio_fingerprint(portfolio, horizon)


def test_aggregate_class_risk_uses_diversification() -> None:
    horizon = RiskHorizon.parse("1y")
    slots = [
        AllocationSlot(asset_class=AssetClass.EQUITY, weight=Decimal("0.5")),
        AllocationSlot(asset_class=AssetClass.CASH, weight=Decimal("0.5")),
    ]
    contribs = [evaluate_class_risk(slot, horizon) for slot in slots]
    undiversified = aggregate_class_risk(contribs, Decimal("1"))
    diversified = aggregate_class_risk(contribs, Decimal("0.85"))
    assert diversified < undiversified


def test_evaluate_portfolio_risk_engine() -> None:
    portfolio = AssetPortfolio.model_validate(_sample_request()["asset_portfolio"])
    report = evaluate_portfolio_risk(portfolio, RiskHorizon.parse("5y"))
    assert report.measurement_summary.measurable_weight == Decimal("0.9")
    assert report.measurement_summary.fermi_weight == Decimal("0.1")


def test_risk_api_http_post_and_get() -> None:
    server = HTTPServer(("127.0.0.1", 0), DashboardHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        import urllib.error
        import urllib.request

        get_req = urllib.request.Request(f"http://127.0.0.1:{port}/api/risk")
        with urllib.request.urlopen(get_req) as resp:
            schema = json.loads(resp.read())
        assert schema["method"] == "POST"

        post_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/risk",
            data=FIXTURE.read_bytes(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(post_req) as resp:
            report = json.loads(resp.read())
        assert report["portfolio_id"] == "demo"
        assert float(report["total_risk"]) > 0
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_evaluate_risk_request_raises_on_missing_horizon() -> None:
    body = _sample_request()
    del body["horizon"]
    with pytest.raises(RiskApiError, match="horizon"):
        evaluate_risk_request(body)
