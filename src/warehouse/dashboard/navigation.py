"""Dashboard page registry — paths and panel ownership."""

from __future__ import annotations

from dataclasses import dataclass

from warehouse.dashboard.status import PLANES, PlaneStatus

_CATALOG_PANELS: tuple[str, ...] = (
    "Platform overview",
    "Phase roadmap",
    "Plane readiness",
    "Workflow catalog",
    "Office Manager gate",
)

_DATA_PANELS: tuple[str, ...] = (
    "Entity graph view",
    "Security master browser",
    "Schema status",
    "Ingest status",
    "Positions & lots",
    "Custodian selector",
    "Alternatives panel",
)

_RESEARCH_PANELS: tuple[str, ...] = (
    "Risk manifest",
    "Backtest results",
    "End-to-end smoke matrix (synthetic)",
)

_RISK_BUILD_PANELS: tuple[str, ...] = ("Risk build tracker",)

_DECISION_PANELS: tuple[str, ...] = (
    "IPS drift monitor",
    "Optimizer proposals",
    "MV rebalance (target weights w*)",
    "Approval queue",
    "Constraint binding report",
    "Synthetic IPS binding matrix",
    "Advisory bundle (pm.advise)",
    "Attribution residuals (attribution.evaluate)",
    "Kill-criteria watch",
    "Non-performing-asset flags",
)

_EXECUTION_PANELS: tuple[str, ...] = (
    "Reconciliation queue",
    "Daily refresh timeline",
    "Staged orders",
    "Solver comparison",
)

_REPORTING_PANELS: tuple[str, ...] = (
    "Household performance",
    "Tax scenario panel",
)

_INFRA_PANELS: tuple[str, ...] = (
    "Infra health",
    "Audit log stream",
    "Postgres migration status",
    "Job queue monitor",
    "Object store health",
)

_TESTING_PANELS: tuple[str, ...] = ("Testing matrix",)


@dataclass(frozen=True)
class DashboardPage:
    """One human-facing dashboard route."""

    page_id: str
    path: str
    title: str
    package: str
    nav_label: str
    panel_names: tuple[str, ...]


PAGES: tuple[DashboardPage, ...] = (
    DashboardPage(
        page_id="catalog",
        path="/",
        title="Catalog",
        package="warehouse.dashboard",
        nav_label="Catalog",
        panel_names=_CATALOG_PANELS,
    ),
    DashboardPage(
        page_id="data",
        path="/data",
        title="Data plane",
        package="warehouse.data",
        nav_label="Data",
        panel_names=_DATA_PANELS,
    ),
    DashboardPage(
        page_id="research",
        path="/research",
        title="Research plane",
        package="warehouse.research",
        nav_label="Research",
        panel_names=_RESEARCH_PANELS,
    ),
    DashboardPage(
        page_id="decision",
        path="/decision",
        title="Decision plane",
        package="warehouse.decision",
        nav_label="Decision",
        panel_names=_DECISION_PANELS,
    ),
    DashboardPage(
        page_id="execution",
        path="/execution",
        title="Execution plane",
        package="warehouse.execution",
        nav_label="Execution",
        panel_names=_EXECUTION_PANELS,
    ),
    DashboardPage(
        page_id="reporting",
        path="/reporting",
        title="Reporting plane",
        package="warehouse.reporting",
        nav_label="Reporting",
        panel_names=_REPORTING_PANELS,
    ),
    DashboardPage(
        page_id="infra",
        path="/infra",
        title="Infrastructure",
        package="warehouse.infra",
        nav_label="Infra",
        panel_names=_INFRA_PANELS,
    ),
    DashboardPage(
        page_id="risk_build",
        path="/risk",
        title="Risk build tracker",
        package="warehouse.research.risk",
        nav_label="Risk build",
        panel_names=_RISK_BUILD_PANELS,
    ),
    DashboardPage(
        page_id="testing",
        path="/testing",
        title="Testing matrix",
        package="warehouse.dashboard",
        nav_label="Testing",
        panel_names=_TESTING_PANELS,
    ),
)

_PLANE_PAGE_BY_PACKAGE: dict[str, DashboardPage] = {
    page.package: page
    for page in PAGES
    if page.page_id not in ("catalog", "infra", "risk_build", "testing")
}

_PANEL_TO_PAGE: dict[str, DashboardPage] = {}
for _page in PAGES:
    for _panel_name in _page.panel_names:
        _PANEL_TO_PAGE[_panel_name] = _page


def page_by_id(page_id: str) -> DashboardPage | None:
    for page in PAGES:
        if page.page_id == page_id:
            return page
    return None


def page_for_panel(panel_name: str) -> DashboardPage:
    return _PANEL_TO_PAGE.get(panel_name, PAGES[0])


def page_for_plane(plane: PlaneStatus) -> DashboardPage | None:
    return _PLANE_PAGE_BY_PACKAGE.get(plane.package)


def live_panel_count(page: DashboardPage) -> int:
    from warehouse.dashboard.phases import PHASES

    live_names = {
        panel.name
        for phase in PHASES
        for panel in phase.panels
        if panel.status == "live"
    }
    return sum(1 for name in page.panel_names if name in live_names)


def plane_pages_for_catalog() -> list[tuple[PlaneStatus, DashboardPage]]:
    rows: list[tuple[PlaneStatus, DashboardPage]] = []
    for plane in PLANES:
        page = page_for_plane(plane)
        if page is not None:
            rows.append((plane, page))
    return rows
