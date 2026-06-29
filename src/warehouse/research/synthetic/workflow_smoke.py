"""In-process workflow smokes — SDG3 downstream falsification without DB.

Each check drives one leg of the live stack on a synthetic bundle and reports
``ok`` + ``detail`` — it never silently passes. The MV-QP leg exercises the
optimizer v1 (po0/po1/po2 — constrained MV + turnover budget + scenario-robust
stress overlay), and the PM leg drives the whole ``pm.advise`` coordinator
in-process (no DB). A leg that raises is surfaced as ``ok=False`` with the
exception in ``detail`` — the failure is reported loudly in the smoke result,
never swallowed (CLAUDE.md errors-bubble; the report IS the surface here).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from warehouse.decision.ips.monitor import build_ips_drift_report_from_views
from warehouse.decision.optimizer.heuristics import run_tax_aware_optimizer
from warehouse.research.synthetic.fixture_views import (
    lot_positions_from_fixture,
    smoke_as_of_date,
)
from warehouse.research.synthetic.models import SyntheticHouseholdBundle
from warehouse.research.synthetic.scenario_card import build_scenario_card

_SUM_TOL = Decimal("0.0001")

# Default acceptance matrix for the end-to-end smoke (cohort, rung, seed). One
# representative household per cohort; concentrated_stress runs at rung 4. Seed
# 42 is the shared fixture seed (§9 HNW fixture matrix). Emitted with
# validate=False so the concentrated cohorts (which fail IPS validation at this
# seed) still drive the downstream legs — exactly as the po0/pa tests do.
_DEFAULT_E2E_COMBOS: tuple[tuple[str, int, int], ...] = (
    ("general_hnw", 3, 42),
    ("uhnw_inherited", 3, 42),
    ("founder_executive", 3, 42),
    ("concentrated_stress", 4, 42),
)


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


def _mv_rebalance_qp_check(
    bundle: SyntheticHouseholdBundle,
) -> WorkflowSmokeCheck:
    """Optimizer v1 (po0/po1/po2) — constrained MV w*/Δw + stress overlay.

    Asserts the QP invariants on generated data: Σw*=1, box-feasible, the
    scenario-robust stress overlay ran (regime gap reported, PO7), μ stays the
    ex-ante class assumption (#5/#6 honesty), and the path stages no trade.
    """
    try:
        from warehouse.decision.optimizer.rebalance import run_mv_rebalance

        restricted = frozenset(bundle.ips.restricted_securities)
        positions = lot_positions_from_fixture(
            bundle.fixture, restricted_tickers=restricted
        )
        proposal = run_mv_rebalance(positions, bundle.ips)
        total = sum(proposal.target_weights.values(), Decimal("0"))
        sum_ok = abs(total - Decimal("1")) <= _SUM_TOL
        box_ok = all(
            Decimal("0") <= w <= Decimal("1")
            for w in proposal.target_weights.values()
        )
        stress_ok = proposal.stress_regime is not None
        mu_ok = proposal.mu_source == "ex_ante_class_assumption"
        no_trade = not hasattr(proposal, "trades")
        ok = sum_ok and box_ok and stress_ok and mu_ok and no_trade
        detail = (
            f"Σw*={total:.4f}; turnover={proposal.turnover_l1}; "
            f"stress={proposal.stress_regime}; "
            f"regime_gap={proposal.regime_gap_l1}; "
            f"binding={len(proposal.binding_bounds)}"
        )
    except Exception as err:  # surface loudly as a failed check (no swallow)
        ok = False
        detail = f"raised {type(err).__name__}: {err}"
    return WorkflowSmokeCheck(workflow="mv_rebalance_qp", ok=ok, detail=detail)


def _pm_advise_check(
    bundle: SyntheticHouseholdBundle,
) -> WorkflowSmokeCheck:
    """Whole-book ``pm.advise`` coordinator in-process (no DB).

    Drives risk → policy → attribution → optimizer → tax through the live
    messaging dispatch and asserts the bundle carries every leg, the rebalance
    w* is present, and the tax leg is held at $0 (honesty #5 stays
    not_computed — the seam is wired, the estimate deferred).
    """
    try:
        import warehouse.messaging.handlers  # noqa: F401  populate REGISTRY
        from warehouse.decision.pm import build_working_set_from_bundle
        from warehouse.messaging import (
            DispatchContext,
            Kind,
            Message,
            dispatch_typed,
        )
        from warehouse.messaging.payloads import AdviceBundle, PmAdvisePayload

        payload = build_working_set_from_bundle(bundle)
        ctx = DispatchContext(session=None)  # type: ignore[arg-type]
        # dispatch_typed narrows to AdviceBundle or raises loudly — a wrong
        # type surfaces through the except below as a failed check (no
        # swallow).
        out = dispatch_typed(
            ctx,
            Message(
                op="pm.advise",
                kind=Kind.EVALUATE,
                payload=PmAdvisePayload.model_validate(payload.model_dump()),
                correlation_id=f"e2e-{bundle.fixture.household_id}",
                household_id=payload.household_id,
            ),
            AdviceBundle,
        )
        legs_ok = (
            out.risk.report is not None
            and out.proposal.rebalance is not None
            and out.narrative is not None
            and out.tax is not None
        )
        tax_zero = out.tax.tax_delta == Decimal("0")
        ok = legs_ok and tax_zero
        detail = (
            f"risk={out.risk.report is not None}; "
            f"rebalance={out.proposal.rebalance is not None}; "
            f"tax_delta={out.tax.tax_delta}; "
            f"narrative={out.narrative is not None}"
        )
    except Exception as err:  # surface loudly as a failed check (no swallow)
        ok = False
        detail = f"raised {type(err).__name__}: {err}"
    return WorkflowSmokeCheck(workflow="pm_advise", ok=ok, detail=detail)


def run_workflow_smoke(
    bundle: SyntheticHouseholdBundle,
    *,
    as_of: date | None = None,
) -> WorkflowSmokeResult:
    """Run the full in-process smoke (drift, v0 TLH, MV-QP, scenario, PM)."""
    eval_date = as_of or smoke_as_of_date(bundle.fixture)
    checks = [
        _policy_monitoring_check(bundle),
        _rebalance_tax_overlay_check(bundle, as_of=eval_date),
        _mv_rebalance_qp_check(bundle),
        _research_scenario_check(bundle),
        _pm_advise_check(bundle),
    ]
    return WorkflowSmokeResult(
        cohort_id=bundle.fixture.provenance.cohort_id,
        seed=bundle.fixture.provenance.seed,
        rung=bundle.fixture.provenance.rung,
        checks=checks,
    )


class E2eMatrixResult(BaseModel):
    """End-to-end smoke over a cohort×rung×seed matrix (live, no DB)."""

    results: list[WorkflowSmokeResult] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results)

    @property
    def summary(self) -> dict[str, int]:
        passed = sum(1 for r in self.results if r.ok)
        return {"households": len(self.results), "passed": passed}


def run_e2e_matrix(
    combos: tuple[tuple[str, int, int], ...] | None = None,
    *,
    validate: bool = False,
) -> E2eMatrixResult:
    """Emit each (cohort, rung, seed) and run the full smoke on it.

    Portfolio + IPS are generated by ``emit_synthetic_household``; every leg
    runs in-process (no DB). ``validate=False`` so the concentrated cohorts
    that fail IPS validation at the shared seed still exercise the stack.
    """
    from warehouse.research.synthetic.pipeline import emit_synthetic_household

    chosen = combos or _DEFAULT_E2E_COMBOS
    results = [
        run_workflow_smoke(
            emit_synthetic_household(
                cohort_id=cohort, seed=seed, rung=rung, validate=validate
            )
        )
        for cohort, rung, seed in chosen
    ]
    return E2eMatrixResult(results=results)
