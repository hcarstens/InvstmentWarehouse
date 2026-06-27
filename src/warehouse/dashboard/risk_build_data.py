"""Risk build tracker — stakeholder view of contract + HNW synthetic progress."""

from __future__ import annotations

import importlib.util

from pydantic import BaseModel, Field

from warehouse.config import repo_root
from warehouse.dashboard.risk_build_registry import (
    BUILD_DOC_LINKS,
    RISK_BUILD_DELIVERABLES,
    SYNTHETIC_IPS_DELIVERABLES,
    SYNTHETIC_IPS_PIPELINE,
    SYNTHETIC_RUNGS,
    BuildDeliverable,
    BuildRung,
)


class BuildSmokeCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class RiskBuildReport(BaseModel):
    contract_status: str  # proposed | v0a | … | v1.2 | si0b | …
    synthetic_ips_status: str  # latest shipped si slice or planned next
    synthetic_ips_pipeline: str
    synthetic_ips_deliverables: list[BuildDeliverable]
    deliverables: list[BuildDeliverable]
    rungs: list[BuildRung]
    doc_links: list[tuple[str, str]]
    shipped_count: int
    planned_count: int
    smoke_checks: list[BuildSmokeCheck] = Field(default_factory=list)


def _module_exists(dotted: str) -> bool:
    return importlib.util.find_spec(dotted) is not None


def _file_exists(rel: str) -> bool:
    return (repo_root() / rel).is_file()


def _run_smoke_checks() -> list[BuildSmokeCheck]:
    checks: list[BuildSmokeCheck] = []

    engine_ok = _module_exists("warehouse.research.risk.engine")
    checks.append(
        BuildSmokeCheck(
            name="risk engine",
            ok=engine_ok,
            detail="evaluate_portfolio_risk importable",
        )
    )

    api_ok = _module_exists("warehouse.research.risk.api")
    checks.append(
        BuildSmokeCheck(
            name="risk HTTP adapter",
            ok=api_ok,
            detail="evaluate_risk_http → evaluate_risk",
        )
    )

    ledger_ok = _file_exists("src/warehouse/research/risk/adapters/ledger.py")
    checks.append(
        BuildSmokeCheck(
            name="ledger manifest adapter",
            ok=ledger_ok,
            detail="build_household_manifest — v0c edge",
        )
    )

    service_ok = _file_exists("src/warehouse/research/risk/service.py")
    checks.append(
        BuildSmokeCheck(
            name="evaluate_risk service",
            ok=service_ok,
            detail="risk/service.py — v0a deliverable",
        )
    )

    synthetic_ok = _file_exists("src/warehouse/research/risk/synthetic.py")
    checks.append(
        BuildSmokeCheck(
            name="synthetic.rung",
            ok=synthetic_ok,
            detail="risk/synthetic.py — v0c deliverable",
        )
    )

    hnw_ok = _file_exists("src/warehouse/research/synthetic/__init__.py")
    checks.append(
        BuildSmokeCheck(
            name="HNW generator package",
            ok=hnw_ok,
            detail="research/synthetic/ — v1 deliverable",
        )
    )

    asset_suite_ok = _file_exists(
        "src/warehouse/research/synthetic/asset_test_suite.py"
    )
    checks.append(
        BuildSmokeCheck(
            name="risk asset test suite",
            ok=asset_suite_ok,
            detail="Phase A/B — leaf types → evaluate_risk → report JSON",
        )
    )

    ips_ok = _file_exists("src/warehouse/decision/ips/sleeves.py")
    checks.append(
        BuildSmokeCheck(
            name="IpsSleeve + policy fields",
            ok=ips_ok,
            detail="decision/ips/sleeves.py — si0a/si0b",
        )
    )

    ips_emit_ok = _file_exists("src/warehouse/research/synthetic/ips_emit.py")
    checks.append(
        BuildSmokeCheck(
            name="emit_ips_for_cohort",
            ok=ips_emit_ok,
            detail="research/synthetic/ips_emit.py — si1",
        )
    )

    ips_validate_ok = _file_exists(
        "src/warehouse/research/synthetic/ips_validate.py"
    )
    checks.append(
        BuildSmokeCheck(
            name="validate_ips + emit_synthetic_household",
            ok=ips_validate_ok,
            detail="research/synthetic/ips_validate.py — si2",
        )
    )

    return checks


def _contract_status(deliverables: list[BuildDeliverable]) -> str:
    by_id = {d.id: d.status for d in deliverables}
    if by_id.get("asset-test-phase-b") == "shipped":
        return "v1.2"
    if by_id.get("hnw-rung4") == "shipped":
        return "v1.1"
    if by_id.get("v1-overlays") == "shipped":
        return "v1"
    if by_id.get("v0c-http") == "shipped":
        return "v0c"
    if by_id.get("v0b-scenarios") == "shipped":
        return "v0b"
    if by_id.get("v0a-envelope") == "shipped":
        return "v0a"
    return "proposed"


def _synthetic_ips_status(slices: list[BuildDeliverable]) -> str:
    shipped = [d for d in slices if d.status == "shipped"]
    if not shipped:
        return "planned"
    latest = max(shipped, key=lambda d: d.slice)
    in_progress = next((d for d in slices if d.status == "in_progress"), None)
    if in_progress:
        return in_progress.slice
    next_planned = next((d for d in slices if d.status == "planned"), None)
    if next_planned:
        return f"{latest.slice} · next {next_planned.slice}"
    return latest.slice


def load_risk_build_report() -> RiskBuildReport:
    deliverables = list(RISK_BUILD_DELIVERABLES)
    synthetic_ips = list(SYNTHETIC_IPS_DELIVERABLES)
    shipped = sum(1 for d in deliverables if d.status == "shipped")
    planned = sum(1 for d in deliverables if d.status == "planned")
    return RiskBuildReport(
        contract_status=_contract_status(deliverables),
        synthetic_ips_status=_synthetic_ips_status(synthetic_ips),
        synthetic_ips_pipeline=SYNTHETIC_IPS_PIPELINE,
        synthetic_ips_deliverables=synthetic_ips,
        deliverables=deliverables,
        rungs=list(SYNTHETIC_RUNGS),
        doc_links=list(BUILD_DOC_LINKS),
        shipped_count=shipped,
        planned_count=planned,
        smoke_checks=_run_smoke_checks(),
    )
