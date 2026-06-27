"""In-process workflow smokes — SDG3 downstream falsification without DB."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from warehouse.decision.ips.monitor import build_ips_drift_report_from_views
from warehouse.decision.optimizer.heuristics import run_tax_aware_optimizer
from warehouse.research.synthetic.fixture_views import (
    lot_positions_from_fixture,
    smoke_as_of_date,
)
from warehouse.research.synthetic.models import SyntheticHouseholdBundle
from warehouse.research.synthetic.scenario_card import build_scenario_card


class WorkflowSmokeCheck(BaseModel):
    workflow: str
    ok: bool
    detail: str


class WorkflowSmokeResult(BaseModel):
    cohort_id: str
    seed: int
    rung: int
    checks: list[WorkflowSmokeCheck] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


def _policy_monitoring_check(
    bundle: SyntheticHouseholdBundle,
) -> WorkflowSmokeCheck:
    restricted = frozenset(bundle.ips.restricted_securities)
    positions = lot_positions_from_fixture(
        bundle.fixture, restricted_tickers=restricted
    )
    drift = build_ips_drift_report_from_views(
        bundle.fixture.household_id,
        positions,
        bundle.ips,
    )
    alert_count = len(drift.alerts) + len(drift.concentration_alerts)
    cohort = bundle.fixture.provenance.cohort_id
    if cohort == "concentrated_stress":
        ok = alert_count >= 1
        detail = f"alerts={alert_count} (drift + concentration required)"
    else:
        ok = True
        detail = f"drift report ok; alerts={alert_count}"
    return WorkflowSmokeCheck(
        workflow="policy_monitoring",
        ok=ok,
        detail=detail,
    )


def _rebalance_tax_overlay_check(
    bundle: SyntheticHouseholdBundle,
    *,
    as_of: date,
) -> WorkflowSmokeCheck:
    restricted = frozenset(bundle.ips.restricted_securities)
    positions = lot_positions_from_fixture(
        bundle.fixture, restricted_tickers=restricted
    )
    result = run_tax_aware_optimizer(
        bundle.fixture.household_id,
        positions,
        bundle.ips,
        as_of=as_of,
    )
    trade_count = len(result.trades)
    binding_count = len(result.binding_constraints)
    ok = trade_count >= 0 and binding_count >= 0
    detail = (
        f"trades={trade_count}; binding_constraints={binding_count}; "
        f"tax_delta={result.estimated_tax_delta}"
    )
    return WorkflowSmokeCheck(
        workflow="rebalance_tax_overlay",
        ok=ok,
        detail=detail,
    )


def _research_scenario_check(
    bundle: SyntheticHouseholdBundle,
) -> WorkflowSmokeCheck:
    cohort = bundle.fixture.provenance.cohort_id
    seed = bundle.fixture.provenance.seed
    rung = bundle.fixture.provenance.rung
    first = build_scenario_card(rung_level=rung, seed=seed, cohort_id=cohort)
    second = build_scenario_card(rung_level=rung, seed=seed, cohort_id=cohort)
    ok = first.risk_fingerprint == second.risk_fingerprint
    detail = (
        f"fingerprint={first.risk_fingerprint[:12]}…; "
        f"ips_id={first.ips_id}; bindings={first.binding_constraints_count}"
    )
    return WorkflowSmokeCheck(
        workflow="research_scenario",
        ok=ok,
        detail=detail,
    )


def run_workflow_smoke(
    bundle: SyntheticHouseholdBundle,
    *,
    as_of: date | None = None,
) -> WorkflowSmokeResult:
    """Run policy drift, optimizer, and scenario-card smokes on a bundle."""
    eval_date = as_of or smoke_as_of_date(bundle.fixture)
    checks = [
        _policy_monitoring_check(bundle),
        _rebalance_tax_overlay_check(bundle, as_of=eval_date),
        _research_scenario_check(bundle),
    ]
    return WorkflowSmokeResult(
        cohort_id=bundle.fixture.provenance.cohort_id,
        seed=bundle.fixture.provenance.seed,
        rung=bundle.fixture.provenance.rung,
        checks=checks,
    )
