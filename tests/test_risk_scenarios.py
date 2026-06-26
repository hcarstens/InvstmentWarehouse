"""Risk scenario catalog — run_scenarios, PSD, golden rung×scenario matrix."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from warehouse.research.risk.models import (
    RiskHorizon,
    RiskRequest,
    ScenarioSet,
)
from warehouse.research.risk.scenarios import assumptions_for, scenario_names
from warehouse.research.risk.service import evaluate_risk
from warehouse.research.risk.synthetic import rung

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "risk_golden"


def test_scenario_catalog_psd_validated_at_import() -> None:
    assert scenario_names() == ("base", "high_risk", "low_risk")


def test_high_risk_raises_vol_vs_base_on_rung_1() -> None:
    portfolio = rung(1)
    horizon = RiskHorizon.parse("5y")
    base = evaluate_risk(
        RiskRequest(horizon=horizon, run_scenarios=ScenarioSet.NONE),
        portfolio,
    )
    alt = evaluate_risk(
        RiskRequest(horizon=horizon, run_scenarios=ScenarioSet.HIGH_RISK),
        portfolio,
    )
    base_vol = base.report.level_1_portfolio.annualized_volatility.value
    high_vol = alt.scenarios["high_risk"].level_1_portfolio.annualized_volatility.value
    assert high_vol > base_vol


def test_run_scenarios_all_returns_two_alternate_reports() -> None:
    result = evaluate_risk(
        RiskRequest(horizon=RiskHorizon.parse("5y"), run_scenarios=ScenarioSet.ALL),
        rung(1),
    )
    assert result.report.manifest.assumption_regime == "base"
    assert set(result.scenarios) == {"high_risk", "low_risk"}
    assert result.scenarios["high_risk"].manifest.assumption_regime == "high_risk"
    assert result.scenarios["low_risk"].manifest.assumption_regime == "low_risk"


def test_fingerprints_differ_by_regime() -> None:
    portfolio = rung(1)
    horizon = RiskHorizon.parse("5y")
    result = evaluate_risk(
        RiskRequest(horizon=horizon, run_scenarios=ScenarioSet.ALL),
        portfolio,
    )
    fingerprints = {
        result.report.input_fingerprint,
        result.scenarios["high_risk"].input_fingerprint,
        result.scenarios["low_risk"].input_fingerprint,
    }
    assert len(fingerprints) == 3


@pytest.mark.parametrize(
    "fixture_name",
    [
        "rung0_none.json",
        "rung0_high_risk.json",
        "rung1_none.json",
        "rung1_high_risk.json",
        "rung2_none.json",
        "rung2_high_risk.json",
    ],
)
def test_golden_rung_scenario_cells(fixture_name: str) -> None:
    cell = json.loads((GOLDEN_DIR / fixture_name).read_text())
    level = cell["rung"]
    scenario_set = ScenarioSet(cell["run_scenarios"])
    portfolio = rung(level)
    request = RiskRequest(
        horizon=RiskHorizon.parse("5y"),
        run_scenarios=scenario_set,
    )
    result = evaluate_risk(request, portfolio)
    if scenario_set == ScenarioSet.NONE:
        report = result.report
    else:
        report = result.scenarios[scenario_set.value]

    expected = cell["expected"]
    assert report.input_fingerprint == expected["input_fingerprint"]
    assert report.manifest.assumption_regime == expected["assumption_regime"]
    assert (
        report.level_1_portfolio.annualized_volatility.value
        == Decimal(expected["annualized_vol"])
    )
    assert (
        report.level_1_portfolio.parametric_var.value
        == Decimal(expected["parametric_var"])
    )


def test_assumptions_for_unknown_regime_raises() -> None:
    with pytest.raises(KeyError, match="unknown assumption regime"):
        assumptions_for("crisis_custom")
