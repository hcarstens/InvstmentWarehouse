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
from warehouse.research.risk.by_class import (
    build_sleeve_states,
    evaluate_class_contributions,
    resolve_measurement,
)
from warehouse.research.risk.by_duration import evaluate_duration_risk
from warehouse.research.risk.covariance import portfolio_covariance
from warehouse.research.risk.engine import evaluate_portfolio_risk
from warehouse.research.risk.fingerprint import portfolio_fingerprint
from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    AssetPortfolio,
    MeasurementMode,
    RiskHorizon,
    RiskUnitType,
)
from warehouse.research.risk.stress import evaluate_stress

FIXTURE = Path(__file__).parent / "fixtures" / "sample_portfolio.json"


def _sample_request() -> dict:
    return json.loads(FIXTURE.read_text())


def test_risk_api_schema_includes_unit_hierarchy() -> None:
    schema = risk_api_schema()
    assert schema["endpoint"] == "/api/risk"
    assert "level_1_portfolio" in schema["response"]
    assert "level_4_stress" in schema["response"]
    assert "docs/research/risk_units_measures.md" in schema["reference"]


def test_evaluate_risk_request_returns_manifest() -> None:
    result = evaluate_risk_request(_sample_request())
    assert result["portfolio_id"] == "demo"
    assert float(result["horizon_years"]) == 5
    assert result["model_version"] == "2026.02"
    assert len(result["input_fingerprint"]) == 16

    level_1 = result["level_1_portfolio"]
    assert level_1["annualized_volatility"]["unit_type"] == RiskUnitType.SIGMA_ANNUALIZED
    assert float(level_1["annualized_volatility"]["value"]) > 0
    assert level_1["parametric_var"]["confidence"] == "0.95"
    assert level_1["parametric_es"]["confidence"] == "0.975"
    assert float(level_1["parametric_var"]["value"]) > 0

    level_2 = result["level_2_contributions"]
    assert len(level_2["by_class"]) == 3
    assert len(level_2["by_duration"]) >= 2
    pct_sum = sum(float(row["pct_variance_contribution"])
                  for row in level_2["by_class"])
    assert pct_sum == pytest.approx(1.0, rel=1e-4)

    level_3 = result["level_3_sensitivities"]["by_sleeve"]
    assert any(row["native_unit"] == RiskUnitType.BETA for row in level_3)
    assert any(row["native_unit"] ==
               RiskUnitType.DURATION_YEARS for row in level_3)

    level_4 = result["level_4_stress"]["scenarios"]
    assert {s["name"] for s in level_4} == {
        "2008_liquidity", "2020_pandemic", "2022_inflation"}

    assert float(result["liquidity"]["weighted_days"]["value"]) > 0
    assert result["aggregation_note"]


def test_notional_enables_dollar_tail_metrics() -> None:
    body = _sample_request()
    body["notional_usd"] = 10_000_000
    result = evaluate_risk_request(body)
    level_1 = result["level_1_portfolio"]
    assert level_1["dollar_var"]["unit_type"] == RiskUnitType.USD
    assert float(level_1["dollar_var"]["value"]) > 0
    stress = result["level_4_stress"]["scenarios"][0]
    assert stress["dollar_pnl"]["currency"] == "USD"


def test_evaluate_risk_json_invalid_body() -> None:
    status, body = evaluate_risk_json("{not json")
    assert status == 400
    assert "Invalid JSON" in json.loads(body)["error"]


def test_weights_must_sum_to_one() -> None:
    body = _sample_request()
    body["asset_portfolio"]["allocations"][0]["weight"] = 0.9
    status, _payload = evaluate_risk_json(json.dumps(body))
    assert status == 422


def test_class_measurable_vs_fermi() -> None:
    equity = resolve_measurement(
        AllocationSlot(asset_class=AssetClass.EQUITY, weight=Decimal("0.5"))
    )
    alt = resolve_measurement(
        AllocationSlot(
            asset_class=AssetClass.ALTERNATIVES,
            weight=Decimal("0.5"),
            liquidity_tier=3,
        )
    )
    assert equity == MeasurementMode.MEASURABLE
    assert alt == MeasurementMode.FERMI


def test_covariance_contributions_sum_to_one() -> None:
    portfolio = AssetPortfolio.model_validate(
        _sample_request()["asset_portfolio"])
    states = build_sleeve_states(portfolio.allocations)
    cov = portfolio_covariance(states)
    contribs = evaluate_class_contributions(states, cov)
    total = sum(c.pct_variance_contribution for c in contribs)
    assert total == pytest.approx(Decimal("1"), rel=Decimal("0.0001"))


def test_duration_buckets_and_mismatch() -> None:
    horizon = RiskHorizon.parse("5y")
    portfolio = AssetPortfolio.model_validate(
        _sample_request()["asset_portfolio"])
    states = build_sleeve_states(portfolio.allocations)
    by_class = evaluate_class_contributions(
        states, portfolio_covariance(states))
    by_duration = evaluate_duration_risk(
        portfolio.allocations, horizon, by_class)
    medium = next(row for row in by_duration if row.bucket == "medium")
    assert float(medium.horizon_mismatch) == pytest.approx(0.35, rel=1e-3)


def test_fingerprint_stable_and_changes_with_notional() -> None:
    portfolio = AssetPortfolio.model_validate(
        _sample_request()["asset_portfolio"])
    horizon = RiskHorizon.parse("5y")
    base = portfolio_fingerprint(portfolio, horizon)
    assert base == portfolio_fingerprint(portfolio, horizon)
    assert portfolio_fingerprint(
        portfolio, horizon, notional_usd=Decimal("1000000")) != base


def test_stress_scenarios_are_linear_sleeve_sum() -> None:
    portfolio = AssetPortfolio.model_validate(
        _sample_request()["asset_portfolio"])
    stress = evaluate_stress(portfolio.allocations,
                             notional_usd=None, mark_source="model_prior")
    scenario = next(s for s in stress.scenarios if s.name == "2022_inflation")
    sleeve_sum = sum(scenario.by_class.values(), Decimal("0"))
    assert sleeve_sum == scenario.portfolio_return.value


def test_evaluate_portfolio_risk_engine() -> None:
    portfolio = AssetPortfolio.model_validate(
        _sample_request()["asset_portfolio"])
    report = evaluate_portfolio_risk(portfolio, RiskHorizon.parse("5y"))
    assert report.measurement_summary.measurable_weight == Decimal("0.9")
    assert report.measurement_summary.fermi_weight == Decimal("0.1")
    assert report.manifest.vol_window_days == 252


def test_risk_api_http_post_and_get() -> None:
    server = HTTPServer(("127.0.0.1", 0), DashboardHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        import urllib.request

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/risk") as resp:
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
        assert float(report["level_1_portfolio"]
                     ["annualized_volatility"]["value"]) > 0
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_evaluate_risk_request_raises_on_missing_horizon() -> None:
    body = _sample_request()
    del body["horizon"]
    with pytest.raises(RiskApiError, match="horizon"):
        evaluate_risk_request(body)
