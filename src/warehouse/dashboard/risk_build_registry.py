"""Risk API + HNW synthetic build tracker.

Keep in sync with the implementation plan. Update deliverable status when a PR
lands: planned | in_progress | shipped. Synthetic IPS slices (si0a–si4) are
listed first — see render_risk_build.py.
"""

from __future__ import annotations

from pydantic import BaseModel


class BuildDeliverable(BaseModel):
    id: str
    track: str  # risk_contract | hnw_synthetic | synthetic_ips
    slice: str  # v0a | v0b | si0a | ...
    name: str
    status: str  # planned | in_progress | shipped | deferred | retired
    doc_href: str
    note: str
    depends_on: list[str] = []
    falsifier_test: str | None = None


class BuildRung(BaseModel):
    rung: int
    owner: str
    status: str
    cohort: str
    exercises: str


# Synthetic IPS track — prepended on risk build dashboard (si0a → si4).
SYNTHETIC_IPS_DELIVERABLES: list[BuildDeliverable] = [
    BuildDeliverable(
        id="si0a-asset-class",
        track="synthetic_ips",
        slice="si0a",
        name="AllocationTarget → IpsSleeve enum + security rollup",
        status="shipped",
        doc_href=(
            "docs/synthetic_ips_implementation.md"
            "#si0a--asset-class-vocabulary--ips-schema-1-pr"
        ),
        note="IpsSleeve enum; monitor/optimizer use security rollup",
        falsifier_test="tests/test_ips_sleeves.py",
    ),
    BuildDeliverable(
        id="si0b-ips-fields",
        track="synthetic_ips",
        slice="si0b",
        name="IPS concentration / liquidity / turnover fields",
        status="shipped",
        doc_href=(
            "docs/synthetic_ips_implementation.md"
            "#si0b--policy-fields--monitor-wiring-1-pr"
        ),
        note="Policy-driven concentration; constraints_json persistence",
        depends_on=["si0a-asset-class"],
        falsifier_test="tests/test_ips_policy_fields.py",
    ),
    BuildDeliverable(
        id="si1-emit-ips",
        track="synthetic_ips",
        slice="si1",
        name="emit_ips_for_cohort",
        status="shipped",
        doc_href=(
            "docs/synthetic_ips_implementation.md"
            "#si1--synthetic-ips-generator-1-pr"
        ),
        note="Cohort-conditioned IPS co-generated with fixture weights",
        depends_on=["si0b-ips-fields"],
        falsifier_test="tests/test_synthetic_ips.py",
    ),
    BuildDeliverable(
        id="si2-validate-ips",
        track="synthetic_ips",
        slice="si2",
        name="validate_ips + emit_synthetic_household bundle",
        status="shipped",
        doc_href=(
            "docs/synthetic_ips_implementation.md"
            "#si2--validate_ips--pipeline-integration-1-pr"
        ),
        note="SDG1 gate; binding_constraints before fixture sealed",
        depends_on=["si1-emit-ips"],
        falsifier_test="tests/test_synthetic_ips.py",
    ),
    BuildDeliverable(
        id="si3-workflow-smoke",
        track="synthetic_ips",
        slice="si3",
        name="In-process workflow smokes + scenario card IPS",
        status="shipped",
        doc_href=(
            "docs/synthetic_ips_implementation.md"
            "#si3--workflow-smokes--scenario-card-1-pr"
        ),
        note="Drift + optimizer smoke; concentrated_stress must bind",
        depends_on=["si2-validate-ips"],
        falsifier_test="tests/test_synthetic_ips_workflow.py",
    ),
    BuildDeliverable(
        id="si4-dashboard-seed",
        track="synthetic_ips",
        slice="si4",
        name="Synthetic IPS dashboard panel + DB seed adapter",
        status="shipped",
        doc_href=(
            "docs/synthetic_ips_implementation.md"
            "#si4--dashboard--seed-adapter-1-pr"
        ),
        note="cohort × binding matrix; seed_synthetic_household",
        depends_on=["si2-validate-ips"],
        falsifier_test="tests/test_synthetic_ips_integration.py",
    ),
]

RISK_HNW_DELIVERABLES: list[BuildDeliverable] = [
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
        status="shipped",
        doc_href=(
            "docs/risk_api_implementation_plan.md"
            "#v0b--scenario-catalog-largest-chunk--2-prs"
        ),
        note="scenarios.py, PSD validation, golden rung×scenario",
    ),
    BuildDeliverable(
        id="v0c-synthetic",
        track="risk_contract",
        slice="v0c",
        name="synthetic.rung(0..2)",
        status="shipped",
        doc_href="docs/risk_api_implementation_plan.md#v0c--integration-2-prs",
        note="Hand-built sleeves in risk/synthetic.py",
    ),
    BuildDeliverable(
        id="v0c-ledger",
        track="risk_contract",
        slice="v0c",
        name="build_household_manifest + slim risk_data",
        status="shipped",
        doc_href="docs/risk_api_contract.md",
        note="Ledger adapter at edge; narrow except",
    ),
    BuildDeliverable(
        id="v0c-http",
        track="risk_contract",
        slice="v0c",
        name="POST /api/risk → evaluate_risk",
        status="shipped",
        doc_href="docs/risk_api_contract.md",
        note="Extend schema with run_scenarios; back-compat JSON",
    ),
    BuildDeliverable(
        id="v1-overlays",
        track="risk_contract",
        slice="v1",
        name="Overlays + RiskDeltas",
        status="shipped",
        doc_href="docs/risk_api_contract.md#v1--overlays--deltas",
        note="Envelope slot reserved in v0",
    ),
    BuildDeliverable(
        id="hnw-generator",
        track="hnw_synthetic",
        slice="v1",
        name="Compositional HNW generator (Shape B)",
        status="shipped",
        doc_href="docs/research/hnw_portfolios.md",
        note="warehouse/research/synthetic/ — cohort → graph → lots",
    ),
    BuildDeliverable(
        id="hnw-rung3",
        track="hnw_synthetic",
        slice="v1",
        name="Rung 3 — 5-sleeve + liquidity tiers",
        status="shipped",
        doc_href="docs/research/hnw_portfolios.md#rung-ladder",
        note="general_hnw, uhnw_inherited cohort priors",
    ),
    BuildDeliverable(
        id="hnw-rung4",
        track="hnw_synthetic",
        slice="v1.1",
        name="Rung 4 — lots + concentration + alt calls",
        status="shipped",
        doc_href="docs/research/hnw_portfolios.md#rung-ladder",
        note="founder_executive, concentrated_stress",
    ),
    BuildDeliverable(
        id="asset-test-phase-a",
        track="hnw_synthetic",
        slice="v1.2",
        name="Risk asset test suite — Phase A (singles)",
        status="shipped",
        doc_href=(
            "docs/risk_api_implementation_plan.md"
            "#12-hnw-leaf-type-combinatorial-harness-v12--shipped"
        ),
        note="Walk each HNW leaf type → evaluate_risk → write report JSON",
    ),
    BuildDeliverable(
        id="asset-test-phase-b",
        track="hnw_synthetic",
        slice="v1.2",
        name="Risk asset test suite — Phase B (combinations)",
        status="shipped",
        doc_href=(
            "docs/risk_api_implementation_plan.md"
            "#12-hnw-leaf-type-combinatorial-harness-v12--shipped"
        ),
        note="Walk 2+ leaf combos → evaluate_risk → write report JSON",
    ),
]

QA_PLAN_DELIVERABLES: list[BuildDeliverable] = [
    BuildDeliverable(
        id="qa3-wash-sale-properties",
        track="qa_plan",
        slice="qa3",
        name="Wash-sale window property falsifiers",
        status="shipped",
        doc_href="docs/qa_plan_implementation.md#7-gap-backlog--qa-implementation-slices",
        note=(
            "Transitive chain merge via assign_wash_sale_chain_ids; "
            "property oracle on random lot streams"
        ),
        falsifier_test="tests/test_lot_properties.py",
    ),
    BuildDeliverable(
        id="qa5-optimizer-edges",
        track="qa_plan",
        slice="qa5",
        name="Near-singular Σ + all-constraints-binding QP edges",
        status="shipped",
        doc_href="docs/qa_plan_implementation.md#7-gap-backlog--qa-implementation-slices",
        note="Raises on infeasible box; fixed point when w_min = w_max",
        falsifier_test="tests/test_optimizer_properties.py",
    ),
    BuildDeliverable(
        id="qa7-after-tax-ytd",
        track="qa_plan",
        slice="qa7",
        name="After-tax return YTD with hand-math oracle",
        status="shipped",
        doc_href="docs/qa_plan_implementation.md#7-gap-backlog--qa-implementation-slices",
        note="compute_after_tax_return_ytd; version-pinned LTCG drag",
        falsifier_test="tests/test_reporting_performance.py",
    ),
    BuildDeliverable(
        id="qa1-break-taxonomy",
        track="qa_plan",
        slice="qa1",
        name="Multi-custodian reconciliation break taxonomy",
        status="shipped",
        doc_href="docs/qa_plan_implementation.md#7-gap-backlog--qa-implementation-slices",
        note=(
            "ReconBreakType on breaks + symbology_mismatch "
            "+ dashboard Type column"
        ),
        falsifier_test="tests/test_phase4.py",
    ),
    BuildDeliverable(
        id="qa2-oms-transitions",
        track="qa_plan",
        slice="qa2",
        name="OMS cancel/replace transition boundaries",
        status="shipped",
        doc_href="docs/qa_plan_implementation.md#7-gap-backlog--qa-implementation-slices",
        note=(
            "Allowed-edge guard on update_order_status; "
            "replace raises NotImplementedError"
        ),
        falsifier_test="tests/test_phase4.py",
    ),
]

RISK_BUILD_DELIVERABLES: list[BuildDeliverable] = (
    SYNTHETIC_IPS_DELIVERABLES + RISK_HNW_DELIVERABLES + QA_PLAN_DELIVERABLES
)

SYNTHETIC_IPS_PIPELINE = "si0a → si0b → si1 → si2 → si3 → si4"

SYNTHETIC_RUNGS: list[BuildRung] = [
    BuildRung(
        rung=0,
        owner="risk/synthetic.py",
        status="shipped",
        cohort="—",
        exercises="Level 1 σ/VaR smoke",
    ),
    BuildRung(
        rung=1,
        owner="risk/synthetic.py",
        status="shipped",
        cohort="—",
        exercises="60/40, duration bucket",
    ),
    BuildRung(
        rung=2,
        owner="risk/synthetic.py",
        status="shipped",
        cohort="—",
        exercises="+ commodities + FX",
    ),
    BuildRung(
        rung=3,
        owner="research/synthetic/",
        status="shipped",
        cohort="general_hnw",
        exercises="5-sleeve, liquidity tiers",
    ),
    BuildRung(
        rung=4,
        owner="research/synthetic/",
        status="shipped",
        cohort="concentrated_stress",
        exercises="lots, concentration, alt calls",
    ),
]

BUILD_DOC_LINKS: list[tuple[str, str]] = [
    ("Dev contract registry", "docs/dev_contract_registry.md"),
    ("Synthetic IPS plan", "docs/synthetic_ips_implementation.md"),
    ("Synthetic IPS design", "docs/research/synthetic_ips.md"),
    ("Risk API contract", "docs/risk_api_contract.md"),
    ("Implementation plan", "docs/risk_api_implementation_plan.md"),
    ("HNW portfolios research", "docs/research/hnw_portfolios.md"),
    ("Risk units (Levels 1–4)", "docs/research/risk_units_measures.md"),
]
