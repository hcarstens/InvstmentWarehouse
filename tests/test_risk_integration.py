"""Ledger adapter and v0c integration tests."""

from __future__ import annotations

import json
import threading
from decimal import Decimal
from http.server import HTTPServer

import pytest

from warehouse.dashboard.risk_data import load_risk_dashboard
from warehouse.dashboard.server import DashboardHandler
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.research.risk.adapters.ledger import build_household_manifest
from warehouse.research.risk.api import evaluate_risk_request
from warehouse.research.risk.models import (
    AssetClass,
    RiskHorizon,
    RiskRequest,
    ScenarioSet,
)
from warehouse.research.risk.service import evaluate_risk
from warehouse.research.risk.synthetic import rung


def test_build_household_manifest_tags_ledger_source() -> None:
    manifest = build_household_manifest(DEMO_HOUSEHOLD_ID)
    assert manifest.portfolio.source == "ledger"
    assert manifest.portfolio.portfolio_id == DEMO_HOUSEHOLD_ID
    total = sum(slot.weight for slot in manifest.portfolio.allocations)
    assert total == Decimal("1")
    assert manifest.notional_usd is not None
    assert manifest.notional_usd > 0


def test_build_household_manifest_matches_evaluate_risk_dashboard() -> None:
    manifest = build_household_manifest(DEMO_HOUSEHOLD_ID)
    horizon = RiskHorizon.parse("5y")
    request = RiskRequest(
        horizon=horizon,
        notional_usd=manifest.notional_usd,
        run_scenarios=ScenarioSet.NONE,
    )
    direct = evaluate_risk(request, manifest.portfolio)
    dashboard = load_risk_dashboard(
        DEMO_HOUSEHOLD_ID, horizon_years=horizon.years
    )
    assert dashboard.error is None
    assert dashboard.report is not None
    assert dashboard.source == "ledger"
    assert (
        dashboard.report.input_fingerprint == direct.report.input_fingerprint
    )


def test_http_post_synthetic_rung2_matches_in_process() -> None:
    portfolio = rung(2)
    body = {
        "asset_portfolio": json.loads(portfolio.model_dump_json()),
        "horizon": "5y",
    }
    in_process = evaluate_risk_request(body)

    server = HTTPServer(("127.0.0.1", 0), DashboardHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        import urllib.request

        post_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/risk",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(post_req) as resp:
            via_http = json.loads(resp.read())
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert via_http["input_fingerprint"] == in_process["input_fingerprint"]
    assert (
        via_http["level_1_portfolio"]["annualized_volatility"]["value"]
        == in_process["level_1_portfolio"]["annualized_volatility"]["value"]
    )


def test_load_risk_dashboard_programming_error_bubbles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(_household_id: str) -> None:
        raise KeyError("missing_column")

    monkeypatch.setattr(
        "warehouse.dashboard.risk_data.build_household_manifest",
        _boom,
    )
    with pytest.raises(KeyError, match="missing_column"):
        load_risk_dashboard()


def test_rung2_post_has_multi_asset_classes() -> None:
    portfolio = rung(2)
    classes = {slot.asset_class for slot in portfolio.allocations}
    assert AssetClass.COMMODITIES in classes
    assert AssetClass.FX in classes
