"""Scenario catalog cards — Shape C provenance for historic replay."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from warehouse.config import repo_root
from warehouse.research.risk.models import (
    RiskHorizon,
    RiskRequest,
    ScenarioSet,
)
from warehouse.research.risk.service import evaluate_risk
from warehouse.research.synthetic.cohort import default_cohort_for_rung
from warehouse.research.synthetic.pipeline import emit_hnw_fixture


class ScenarioCard(BaseModel):
    scenario_id: str
    cohort_id: str
    seed: int
    rung: int
    generator_version: str
    horizon_years: str = "5"
    run_scenarios: str = ScenarioSet.NONE.value
    risk_fingerprint: str
    tension_tags: list[str] = []


def build_scenario_card(
    *,
    rung_level: int,
    seed: int,
    cohort_id: str | None = None,
    run_scenarios: ScenarioSet = ScenarioSet.NONE,
) -> ScenarioCard:
    cohort = cohort_id or default_cohort_for_rung(rung_level)
    fixture = emit_hnw_fixture(cohort_id=cohort, seed=seed, rung=rung_level)
    portfolio = fixture.asset_portfolio
    if portfolio is None:
        raise RuntimeError("HNW fixture missing Shape A projection")
    horizon = RiskHorizon.parse("5y")
    result = evaluate_risk(
        RiskRequest(horizon=horizon, run_scenarios=run_scenarios),
        portfolio,
    )
    return ScenarioCard(
        scenario_id=f"{portfolio.cohort_id}-r{rung_level}-s{seed}",
        cohort_id=portfolio.cohort_id or "unknown",
        seed=seed,
        rung=rung_level,
        generator_version=portfolio.generator_version or "unknown",
        run_scenarios=run_scenarios.value,
        risk_fingerprint=result.report.input_fingerprint,
        tension_tags=list(portfolio.tension_tags),
    )


def default_cards_dir() -> Path:
    return repo_root() / "runs" / "research" / "scenario_cards"


def write_scenario_card(
    card: ScenarioCard, directory: Path | None = None
) -> Path:
    out_dir = directory or default_cards_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{card.scenario_id}.json"
    path.write_text(json.dumps(card.model_dump(), indent=2) + "\n")
    return path
