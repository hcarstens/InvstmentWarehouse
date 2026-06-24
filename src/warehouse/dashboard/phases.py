"""Phase roadmap — keep in sync with TODO.md dashboard panels."""

from pydantic import BaseModel


class DashboardPanel(BaseModel):
    name: str
    phase: int
    status: str  # live | stub | planned


class Phase(BaseModel):
    number: int
    name: str
    dashboard_summary: str
    status: str  # complete | in_progress | planned
    panels: list[DashboardPanel]


PHASES: list[Phase] = [
    Phase(
        number=0,
        name="Shell + dashboard foundation",
        dashboard_summary=(
            "Platform overview, phase roadmap, plane readiness, workflow catalog, infra health"
        ),
        status="complete",
        panels=[
            DashboardPanel(name="Platform overview", phase=0, status="live"),
            DashboardPanel(name="Phase roadmap", phase=0, status="live"),
            DashboardPanel(name="Plane readiness", phase=0, status="live"),
            DashboardPanel(name="Workflow catalog", phase=0, status="live"),
            DashboardPanel(name="Infra health", phase=0, status="live"),
        ],
    ),
    Phase(
        number=1,
        name="Discovery, schema & data model views",
        dashboard_summary="Entity graph explorer, security master table, schema/migration status",
        status="planned",
        panels=[
            DashboardPanel(name="Entity graph view", phase=1, status="planned"),
            DashboardPanel(name="Security master browser", phase=1, status="planned"),
            DashboardPanel(name="Schema status", phase=1, status="planned"),
        ],
    ),
    Phase(
        number=2,
        name="Vertical slice & positions dashboard",
        dashboard_summary="Live positions, ingest pipeline, reconciliation exceptions, daily P&L",
        status="planned",
        panels=[
            DashboardPanel(name="Ingest status", phase=2, status="planned"),
            DashboardPanel(name="Positions & lots", phase=2, status="planned"),
            DashboardPanel(name="Reconciliation queue", phase=2, status="planned"),
            DashboardPanel(name="Daily refresh timeline", phase=2, status="planned"),
            DashboardPanel(name="Audit log stream", phase=2, status="planned"),
        ],
    ),
    Phase(
        number=3,
        name="Decision plane & optimizer dashboard",
        dashboard_summary="IPS drift, optimizer proposals, approval queue, backtest outcomes",
        status="planned",
        panels=[
            DashboardPanel(name="IPS drift monitor", phase=3, status="planned"),
            DashboardPanel(name="Optimizer proposals", phase=3, status="planned"),
            DashboardPanel(name="Approval queue", phase=3, status="planned"),
            DashboardPanel(name="Backtest results", phase=3, status="planned"),
            DashboardPanel(name="Constraint binding report", phase=3, status="planned"),
        ],
    ),
    Phase(
        number=4,
        name="Execution & alternatives (deferred)",
        dashboard_summary="Staged orders, solver comparison, multi-custodian, alt sub-ledger",
        status="planned",
        panels=[
            DashboardPanel(name="Staged orders", phase=4, status="planned"),
            DashboardPanel(name="Solver comparison", phase=4, status="planned"),
            DashboardPanel(name="Custodian selector", phase=4, status="planned"),
            DashboardPanel(name="Alternatives panel", phase=4, status="planned"),
            DashboardPanel(name="Tax scenario panel", phase=4, status="planned"),
        ],
    ),
]
