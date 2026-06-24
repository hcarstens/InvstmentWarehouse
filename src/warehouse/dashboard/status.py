"""Aggregate live system state for the dashboard."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse import __version__
from warehouse.config import get_settings
from warehouse.dashboard.phases import PHASES, Phase
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
    live_panel_count: int
    planned_panel_count: int


PLANES: list[PlaneStatus] = [
    PlaneStatus(name="Data", package="warehouse.data", readiness="partial", note="Models defined; ingest pending"),
    PlaneStatus(name="Research", package="warehouse.research", readiness="stub", note="Backtest harness scaffolded"),
    PlaneStatus(name="Decision", package="warehouse.decision", readiness="partial", note="IPS/optimizer models only"),
    PlaneStatus(name="Execution", package="warehouse.execution", readiness="stub", note="Deferred until reconciliation v0"),
    PlaneStatus(name="Reporting", package="warehouse.reporting", readiness="stub", note="Performance model only"),
]


def build_status_report() -> StatusReport:
    settings = get_settings()
    all_panels = [panel for phase in PHASES for panel in phase.panels]
    return StatusReport(
        app_env=settings.app_env,
        build_order="ledger + security master → entity graph → optimizer → OMS",
        north_star="after-tax wealth maximization",
        phases=PHASES,
        planes=PLANES,
        workflows=WORKFLOW_CATALOG,
        live_panel_count=sum(1 for p in all_panels if p.status == "live"),
        planned_panel_count=sum(1 for p in all_panels if p.status != "live"),
    )
