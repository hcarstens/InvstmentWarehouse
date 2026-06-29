"""Aggregate live system state for the dashboard."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse import __version__
from warehouse.config import get_settings
from warehouse.dashboard.phases import PHASES, Phase
from warehouse.infra.health import InfraCheck, run_infra_checks
from warehouse.workflows.catalog import WORKFLOW_CATALOG, WorkflowDefinition


class PlaneStatus(BaseModel):
    name: str
    package: str
    readiness: str  # stub | partial | live
    note: str


class StatusReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = __version__
    app_env: str
    build_order: str
    north_star: str
    phases: list[Phase]
    planes: list[PlaneStatus]
    workflows: list[WorkflowDefinition]
    infra_checks: list[InfraCheck]
    live_panel_count: int
    planned_panel_count: int
    infra_error_count: int


PLANES: list[PlaneStatus] = [
    PlaneStatus(
        name="Data",
        package="warehouse.data",
        readiness="live",
        note="Entity graph, security master, lot schema in SQLite",
    ),
    PlaneStatus(
        name="Research",
        package="warehouse.research",
        readiness="live",
        note="Walk-forward backtest harness; portfolio risk API (class + duration)",
    ),
    PlaneStatus(
        name="Decision",
        package="warehouse.decision",
        readiness="live",
        note="IPS drift, TLH optimizer v0, advisor approval gates",
    ),
    PlaneStatus(
        name="Execution",
        package="warehouse.execution",
        readiness="live",
        note="Reconciliation v0, OMS staging and order state machine",
    ),
    PlaneStatus(
        name="Reporting",
        package="warehouse.reporting",
        readiness="live",
        note="Household performance P&L; reporting-owned tax scenarios",
    ),
]


def build_status_report() -> StatusReport:
    settings = get_settings()
    all_panels = [panel for phase in PHASES for panel in phase.panels]
    infra_checks = run_infra_checks(settings)
    return StatusReport(
        app_env=settings.app_env,
        build_order="ledger + security master → entity graph → optimizer → OMS",
        north_star="after-tax wealth maximization",
        phases=PHASES,
        planes=PLANES,
        workflows=WORKFLOW_CATALOG,
        infra_checks=infra_checks,
        live_panel_count=sum(1 for p in all_panels if p.status == "live"),
        planned_panel_count=sum(1 for p in all_panels if p.status != "live"),
        infra_error_count=sum(1 for c in infra_checks if c.status == "error"),
    )
