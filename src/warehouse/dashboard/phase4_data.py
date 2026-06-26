"""Phase 4 dashboard data — OMS, solver, custodian, alts, tax scenarios."""

from pydantic import BaseModel

from warehouse.config import repo_root
from warehouse.dashboard.phase3_data import load_phase3_dashboard
from warehouse.data.alternatives.service import (
    AlternativeEventView,
    AlternativeHoldingView,
    list_alternative_events,
    list_alternative_holdings,
)
from warehouse.data.ingest.custodian_views import (
    CustodianSummary,
    list_custodians,
    list_ingest_runs_for_custodian,
    list_lot_positions_for_custodian,
)
from warehouse.data.ingest.runner import IngestRunSummary, run_custodian_ingest
from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.approval import ApprovalStatus
from warehouse.decision.approval.service import (
    list_approval_requests,
    update_approval_status,
)
from warehouse.decision.optimizer.compare import (
    SolverComparisonView,
    list_solver_comparisons,
    run_solver_comparison,
)
from warehouse.decision.tax.scenarios import (
    TaxScenarioOverlays,
    TaxScenarioRunView,
    list_tax_scenarios,
    run_tax_scenario,
)
from warehouse.execution.oms.service import StagedOrderView, list_staged_orders
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID


class Phase4DashboardData(BaseModel):
    household_id: str
    selected_custodian_id: str
    custodians: list[CustodianSummary]
    staged_orders: list[StagedOrderView]
    solver_comparisons: list[SolverComparisonView]
    custodian_positions: list[LotPositionView]
    custodian_ingest_runs: list[IngestRunSummary]
    alternative_holdings: list[AlternativeHoldingView]
    alternative_events: list[AlternativeEventView]
    tax_scenarios: list[TaxScenarioRunView]
    error: str | None = None


DEFAULT_CUSTODIAN = "custodian_schwab"


def _ensure_demo_phase4() -> None:
    with session_scope() as session:
        if not list_solver_comparisons(session, DEMO_HOUSEHOLD_ID, limit=1):
            run_solver_comparison(session, DEMO_HOUSEHOLD_ID)
        if not list_tax_scenarios(session, DEMO_HOUSEHOLD_ID, limit=1):
            run_tax_scenario(
                session,
                DEMO_HOUSEHOLD_ID,
                scenario_name="niit_overlay",
                overlays=TaxScenarioOverlays(apply_niit=True),
            )
        if not list_staged_orders(session, household_id=DEMO_HOUSEHOLD_ID, limit=1):
            pending = [
                a
                for a in list_approval_requests(session, household_id=DEMO_HOUSEHOLD_ID)
                if a.status == ApprovalStatus.PENDING.value
            ]
            if pending:
                update_approval_status(
                    session,
                    pending[0].request_id,
                    status=ApprovalStatus.APPROVED,
                    reviewer_id="advisor:demo",
                )
        fidelity_runs = list_ingest_runs_for_custodian(
            session, "custodian_fidelity", limit=1)
        if not fidelity_runs:
            run_custodian_ingest(
                session,
                repo_root() / "tests/fixtures/fidelity_positions.csv",
                custodian_id="custodian_fidelity",
                household_id=DEMO_HOUSEHOLD_ID,
            )


def load_phase4_dashboard(custodian_id: str | None = None) -> Phase4DashboardData:
    selected = custodian_id or DEFAULT_CUSTODIAN
    try:
        bootstrap_database(seed=True)
        load_phase3_dashboard()
        _ensure_demo_phase4()
        with session_scope() as session:
            custodians = list_custodians(session)
            orders = list_staged_orders(
                session, household_id=DEMO_HOUSEHOLD_ID)
            comparisons = list_solver_comparisons(session, DEMO_HOUSEHOLD_ID)
            positions = list_lot_positions_for_custodian(
                session,
                household_id=DEMO_HOUSEHOLD_ID,
                custodian_id=selected,
            )
            ingest_runs = list_ingest_runs_for_custodian(session, selected)
            alts = list_alternative_holdings(session, DEMO_HOUSEHOLD_ID)
            alt_events = list_alternative_events(session, DEMO_HOUSEHOLD_ID)
            tax = list_tax_scenarios(session, DEMO_HOUSEHOLD_ID)
        return Phase4DashboardData(
            household_id=DEMO_HOUSEHOLD_ID,
            selected_custodian_id=selected,
            custodians=custodians,
            staged_orders=orders,
            solver_comparisons=comparisons,
            custodian_positions=positions,
            custodian_ingest_runs=ingest_runs,
            alternative_holdings=alts,
            alternative_events=alt_events,
            tax_scenarios=tax,
        )
    except Exception as err:
        return Phase4DashboardData(
            household_id=DEMO_HOUSEHOLD_ID,
            selected_custodian_id=selected,
            custodians=[],
            staged_orders=[],
            solver_comparisons=[],
            custodian_positions=[],
            custodian_ingest_runs=[],
            alternative_holdings=[],
            alternative_events=[],
            tax_scenarios=[],
            error=str(err),
        )
