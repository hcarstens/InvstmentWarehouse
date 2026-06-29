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
            DashboardPanel(name="Testing matrix", phase=0, status="stub"),
        ],
    ),
    Phase(
        number=1,
        name="Discovery, schema & data model views",
        dashboard_summary="Entity graph explorer, security master table, schema/migration status",
        status="complete",
        panels=[
            DashboardPanel(name="Entity graph view", phase=1, status="live"),
            DashboardPanel(
                name="Security master browser", phase=1, status="live"
            ),
            DashboardPanel(name="Schema status", phase=1, status="live"),
        ],
    ),
    Phase(
        number=2,
        name="Vertical slice & positions dashboard",
        dashboard_summary="Live positions, ingest pipeline, reconciliation exceptions, daily P&L",
        status="complete",
        panels=[
            DashboardPanel(name="Ingest status", phase=2, status="live"),
            DashboardPanel(name="Positions & lots", phase=2, status="live"),
            DashboardPanel(name="Risk manifest", phase=2, status="live"),
            DashboardPanel(name="Risk build tracker", phase=2, status="live"),
            DashboardPanel(
                name="Reconciliation queue", phase=2, status="live"
            ),
            DashboardPanel(
                name="Daily refresh timeline", phase=2, status="live"
            ),
            DashboardPanel(name="Audit log stream", phase=2, status="live"),
        ],
    ),
    Phase(
        number=3,
        name="Decision plane & optimizer dashboard",
        dashboard_summary="IPS drift, optimizer proposals, approval queue, backtest outcomes",
        status="complete",
        panels=[
            DashboardPanel(name="IPS drift monitor", phase=3, status="live"),
            DashboardPanel(name="Optimizer proposals", phase=3, status="live"),
            DashboardPanel(
                name="MV rebalance (target weights w*)",
                phase=3,
                status="live",
            ),
            DashboardPanel(name="Approval queue", phase=3, status="live"),
            DashboardPanel(name="Backtest results", phase=3, status="live"),
            DashboardPanel(
                name="Constraint binding report", phase=3, status="live"
            ),
            DashboardPanel(
                name="Synthetic IPS binding matrix", phase=3, status="live"
            ),
            DashboardPanel(
                name="Advisory bundle (pm.advise)", phase=3, status="live"
            ),
            DashboardPanel(name="Office Manager gate", phase=3, status="live"),
            DashboardPanel(
                name="Attribution residuals (attribution.evaluate)",
                phase=3,
                status="live",
            ),
            DashboardPanel(
                name="Kill-criteria watch",
                phase=3,
                status="live",
            ),
            DashboardPanel(
                name="End-to-end smoke matrix (synthetic)",
                phase=3,
                status="live",
            ),
            DashboardPanel(
                name="Non-performing-asset flags",
                phase=3,
                status="live",
            ),
        ],
    ),
    Phase(
        number=4,
        name="Execution, alternatives & tax depth",
        dashboard_summary=(
            "Staged orders, solver comparison, multi-custodian, alt sub-ledger, tax scenarios"
        ),
        status="complete",
        panels=[
            DashboardPanel(name="Staged orders", phase=4, status="live"),
            DashboardPanel(name="Solver comparison", phase=4, status="live"),
            DashboardPanel(name="Custodian selector", phase=4, status="live"),
            DashboardPanel(name="Alternatives panel", phase=4, status="live"),
            DashboardPanel(name="Tax scenario panel", phase=4, status="live"),
        ],
    ),
    Phase(
        number=5,
        name="Prod infra: docker-compose & Postgres",
        dashboard_summary="Postgres ledger, Redis queue, object store, RLS — prod parity",
        status="planned",
        panels=[
            DashboardPanel(
                name="Postgres migration status", phase=5, status="planned"
            ),
            DashboardPanel(
                name="Job queue monitor", phase=5, status="planned"
            ),
            DashboardPanel(
                name="Object store health", phase=5, status="planned"
            ),
        ],
    ),
]
