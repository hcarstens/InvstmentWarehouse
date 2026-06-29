"""MV rebalance panel data (po0) — real synthetic system state.

Drives the optimizer rebalance panel off an in-process ``general_hnw`` rung-3
household (no DB needed, §9): emit → roll positions to sleeve weights → solve
the constrained MV QP → report target-vs-current w, Δw, policy drift, binding
IPS bounds, per-sleeve risk contributions, and the illiquid-sleeve flags.

The rebalance is **advisory** — w*/Δw only; nothing is staged or executed
(CLAUDE.md human gate). μ is an **ex-ante class assumption**, never a forecast
or alpha (PO6). Failures surface in the panel's ``error`` field rather than
disappearing (CLAUDE.md).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from warehouse.config import get_settings
from warehouse.decision.optimizer.rebalance import run_mv_rebalance
from warehouse.research.synthetic import emit_synthetic_household
from warehouse.research.synthetic.fixture_views import (
    lot_positions_from_fixture,
    smoke_as_of_date,
)

_OPT_COHORT = "general_hnw"
_OPT_SEED = 42
_OPT_RUNG = 3

# Honesty label (PO6): μ is an ex-ante class assumption, never a forecast or
# realized alpha. Rendered verbatim on the panel; scanned by
# test_mu_not_named_forecast.
MU_SOURCE_LABEL = "ex-ante class assumption"


class OptimizerSleeveRow(BaseModel):
    sleeve: str
    current_weight: Decimal
    target_weight: Decimal
    delta_w: Decimal
    policy_drift: Decimal
    risk_contribution: Decimal
    illiquid: bool = False
    unbounded: bool = False


class OptimizerPanelData(BaseModel):
    household_id: str
    cohort_id: str
    as_of_date: date
    config_version: str
    mu_source: str
    mu_source_label: str
    lam: Decimal
    rows: list[OptimizerSleeveRow]
    binding_bounds: list[str]
    turnover_l1: Decimal
    # po1 turnover budget (§B.3): the hard ‖Δw‖₁ ≤ τ cap. ``turnover_budget``
    # here is a DEMO-ONLY pin injected by the loader (the cohort IPS sets no
    # budget); ``turnover_status`` flips the panel line "reported" → "within
    # budget"/"capped at budget".
    turnover_budget: Decimal | None = None
    turnover_binding: bool = False
    unconstrained_turnover_l1: Decimal = Decimal("0")
    turnover_budget_is_demo: bool = False
    objective_value: Decimal
    panel_status: str = "live"
    error: str | None = None

    @property
    def turnover_status(self) -> str:
        """Human label for the turnover line (reported → constrained, §B.3)."""
        if self.turnover_budget is None:
            return "reported (no budget)"
        if self.turnover_binding:
            return "capped at budget"
        return "within budget"


def load_optimizer_dashboard() -> OptimizerPanelData:
    try:
        bundle = emit_synthetic_household(
            cohort_id=_OPT_COHORT,
            seed=_OPT_SEED,
            rung=_OPT_RUNG,
        )
        fixture = bundle.fixture
        as_of = smoke_as_of_date(fixture)
        restricted = frozenset(bundle.ips.restricted_securities)
        positions = lot_positions_from_fixture(
            fixture, restricted_tickers=restricted
        )
        # DEMO-ONLY turnover budget: the §9 cohort IPS leaves
        # turnover_budget_pct unset, so inject a labelled pin (model_copy) to
        # show a live within-budget/capped state on the panel (§B.3). Not a
        # household policy.
        cfg = get_settings()
        demo_budget = Decimal(str(cfg.optimizer_demo_turnover_budget_pct))
        ips = bundle.ips.model_copy(
            update={"turnover_budget_pct": demo_budget}
        )
        proposal = run_mv_rebalance(positions, ips)

        illiquid = set(proposal.illiquid_advisory_sleeves)
        unbounded = set(proposal.unbounded_sleeves)
        rows = [
            OptimizerSleeveRow(
                sleeve=sleeve.value,
                current_weight=proposal.current_weights[sleeve],
                target_weight=proposal.target_weights[sleeve],
                delta_w=proposal.delta_w[sleeve],
                policy_drift=proposal.policy_drift[sleeve],
                risk_contribution=proposal.risk_contributions[sleeve],
                illiquid=sleeve in illiquid,
                unbounded=sleeve in unbounded,
            )
            for sleeve in proposal.target_weights
        ]
        return OptimizerPanelData(
            household_id=fixture.household_id,
            cohort_id=_OPT_COHORT,
            as_of_date=as_of,
            config_version=proposal.config_version,
            mu_source=proposal.mu_source,
            mu_source_label=MU_SOURCE_LABEL,
            lam=proposal.lam,
            rows=rows,
            binding_bounds=proposal.binding_bounds,
            turnover_l1=proposal.turnover_l1,
            turnover_budget=proposal.turnover_budget,
            turnover_binding=proposal.turnover_binding,
            unconstrained_turnover_l1=proposal.unconstrained_turnover_l1,
            turnover_budget_is_demo=True,
            objective_value=proposal.objective_value,
        )
    except Exception as err:
        return OptimizerPanelData(
            household_id="(unavailable)",
            cohort_id=_OPT_COHORT,
            as_of_date=date.today(),
            config_version="(unavailable)",
            mu_source="ex_ante_class_assumption",
            mu_source_label=MU_SOURCE_LABEL,
            lam=Decimal("0"),
            rows=[],
            binding_bounds=[],
            turnover_l1=Decimal("0"),
            objective_value=Decimal("0"),
            panel_status="error",
            error=str(err),
        )
