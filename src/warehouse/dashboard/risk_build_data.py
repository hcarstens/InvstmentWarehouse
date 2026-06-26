"""Risk build tracker — stakeholder view of contract + HNW synthetic progress."""

from __future__ import annotations

import importlib.util

from pydantic import BaseModel, Field

from warehouse.config import repo_root
from warehouse.dashboard.risk_build_registry import (
    BUILD_DOC_LINKS,
    RISK_BUILD_DELIVERABLES,
    SYNTHETIC_RUNGS,
    BuildDeliverable,
    BuildRung,
)


class BuildSmokeCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class RiskBuildReport(BaseModel):
    contract_status: str  # proposed | v0a | v0b | v0c | v1
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


def load_risk_build_report() -> RiskBuildReport:
    deliverables = list(RISK_BUILD_DELIVERABLES)
    shipped = sum(1 for d in deliverables if d.status == "shipped")
    planned = sum(1 for d in deliverables if d.status == "planned")
    return RiskBuildReport(
        contract_status=_contract_status(deliverables),
        deliverables=deliverables,
        rungs=list(SYNTHETIC_RUNGS),
        doc_links=list(BUILD_DOC_LINKS),
        shipped_count=shipped,
        planned_count=planned,
        smoke_checks=_run_smoke_checks(),
    )
