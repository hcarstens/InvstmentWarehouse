"""Risk API + HNW synthetic build tracker — keep in sync with implementation plan.

Update deliverable status when a PR lands: planned | in_progress | shipped.
"""

from __future__ import annotations

from pydantic import BaseModel


class BuildDeliverable(BaseModel):
    id: str
    track: str  # risk_contract | hnw_synthetic
    slice: str  # v0a | v0b | v0c | v1 | v1.1
    name: str
    status: str  # planned | in_progress | shipped
    doc_href: str
    note: str


class BuildRung(BaseModel):
    rung: int
    owner: str
    status: str
    cohort: str
    exercises: str


RISK_BUILD_DELIVERABLES: list[BuildDeliverable] = [
    BuildDeliverable(
        id="v0a-envelope",
        track="risk_contract",
        slice="v0a",
        name="RiskRequest + RiskResult + evaluate_risk",
        status="shipped",
        doc_href="docs/risk_api_implementation_plan.md#v0a--envelope-1-pr",
        note="Wrap evaluate_portfolio_risk; freeze RiskResult",
    ),
    BuildDeliverable(
        id="v0b-scenarios",
        track="risk_contract",
        slice="v0b",
        name="Scenario catalog + run_scenarios",
        status="planned",
        doc_href="docs/risk_api_implementation_plan.md#v0b--scenario-catalog-largest-chunk--2-prs",
        note="scenarios.py, PSD validation, golden rung×scenario",
    ),
    BuildDeliverable(
        id="v0c-synthetic",
        track="risk_contract",
        slice="v0c",
        name="synthetic.rung(0..2)",
        status="planned",
        doc_href="docs/risk_api_implementation_plan.md#v0c--integration-2-prs",
        note="Hand-built sleeves in risk/synthetic.py",
    ),
    BuildDeliverable(
        id="v0c-ledger",
        track="risk_contract",
        slice="v0c",
        name="build_household_manifest + slim risk_data",
        status="planned",
        doc_href="docs/risk_api_contract.md",
        note="Ledger adapter at edge; narrow except",
    ),
    BuildDeliverable(
        id="v0c-http",
        track="risk_contract",
        slice="v0c",
        name="POST /api/risk → evaluate_risk",
        status="planned",
        doc_href="docs/risk_api_contract.md",
        note="Extend schema with run_scenarios; back-compat JSON",
    ),
    BuildDeliverable(
        id="v1-overlays",
        track="risk_contract",
        slice="v1",
        name="Overlays + RiskDeltas",
        status="planned",
        doc_href="docs/risk_api_contract.md#v1--overlays--deltas",
        note="Envelope slot reserved in v0",
    ),
    BuildDeliverable(
        id="hnw-generator",
        track="hnw_synthetic",
        slice="v1",
        name="Compositional HNW generator (Shape B)",
        status="planned",
        doc_href="docs/research/hnw_portfolios.md",
        note="warehouse/research/synthetic/ — cohort → graph → lots",
    ),
    BuildDeliverable(
        id="hnw-rung3",
        track="hnw_synthetic",
        slice="v1",
        name="Rung 3 — 5-sleeve + liquidity tiers",
        status="planned",
        doc_href="docs/research/hnw_portfolios.md#rung-ladder",
        note="general_hnw, uhnw_inherited cohort priors",
    ),
    BuildDeliverable(
        id="hnw-rung4",
        track="hnw_synthetic",
        slice="v1.1",
        name="Rung 4 — lots + concentration + alt calls",
        status="planned",
        doc_href="docs/research/hnw_portfolios.md#rung-ladder",
        note="founder_executive, concentrated_stress",
    ),
]

SYNTHETIC_RUNGS: list[BuildRung] = [
    BuildRung(
        rung=0,
        owner="risk/synthetic.py",
        status="planned",
        cohort="—",
        exercises="Level 1 σ/VaR smoke",
    ),
    BuildRung(
        rung=1,
        owner="risk/synthetic.py",
        status="planned",
        cohort="—",
        exercises="60/40, duration bucket",
    ),
    BuildRung(
        rung=2,
        owner="risk/synthetic.py",
        status="planned",
        cohort="—",
        exercises="+ commodities + FX",
    ),
    BuildRung(
        rung=3,
        owner="research/synthetic/",
        status="planned",
        cohort="general_hnw, uhnw_inherited",
        exercises="5-sleeve, liquidity tiers",
    ),
    BuildRung(
        rung=4,
        owner="research/synthetic/",
        status="planned",
        cohort="founder_executive, concentrated_stress",
        exercises="lots, TLH, recon, call stress",
    ),
]

BUILD_DOC_LINKS: list[tuple[str, str]] = [
    ("Risk API contract", "docs/risk_api_contract.md"),
    ("Implementation plan", "docs/risk_api_implementation_plan.md"),
    ("HNW portfolios research", "docs/research/hnw_portfolios.md"),
    ("Risk units (Levels 1–4)", "docs/research/risk_units_measures.md"),
]
