"""Dashboard status report tests."""

import threading
from http.server import HTTPServer

from warehouse.dashboard.catalog import render_catalog
from warehouse.dashboard.navigation import PAGES
from warehouse.dashboard.phases import PHASES
from warehouse.dashboard.server import DashboardHandler, render_html
from warehouse.dashboard.status import build_status_report


def test_catalog_renders_plane_links() -> None:
    html = render_catalog()
    for page in PAGES:
        assert f'href="{page.path}"' in html


def test_catalog_nav_contains_all_pages() -> None:
    html = render_catalog()
    for page in PAGES:
        assert page.nav_label in html


def test_catalog_does_not_contain_entity_graph() -> None:
    html = render_catalog()
    assert "<h2>Entity graph" not in html


def test_data_page_loads() -> None:
    from warehouse.dashboard.pages.data import render_data_page

    html = render_data_page()
    assert "<h2>Entity graph" in html
    assert "<h2>Security master</h2>" in html
    assert "Schema status" in html
    assert "Ingest status" in html
    assert "Positions" in html and "lots" in html
    assert "Custodian selector" in html
    assert "Alternatives sub-ledger" in html
    assert 'href="/data"' in html or 'action="/data"' in html
    assert "Parametric VaR" not in html


def test_api_pages_data() -> None:
    from warehouse.dashboard.pages.data import load_data_page

    data = load_data_page()
    assert data.phase1.household_id
    assert data.error is None


def test_research_page_loads() -> None:
    from warehouse.dashboard.pages.research import render_research_page

    html = render_research_page()
    assert "Risk manifest" in html
    assert "Level 1" in html
    assert "Parametric VaR" in html
    assert "2008_liquidity" in html
    assert "Backtest results" in html
    assert 'href="/risk"' in html
    assert "Risk build tracker" in html
    assert "IPS drift" not in html
    assert "axiom checklist" not in html


def test_catalog_omits_risk_manifest_detail() -> None:
    html = render_catalog()
    assert "Parametric VaR" not in html
    assert "Level 1" not in html


def test_api_pages_research() -> None:
    from warehouse.dashboard.pages.research import load_research_page

    data = load_research_page()
    assert data.risk.report is not None
    assert data.error is None


def test_decision_page_loads() -> None:
    from warehouse.dashboard.pages.decision import render_decision_page

    html = render_decision_page()
    assert "IPS drift monitor" in html
    assert "Optimizer proposals" in html
    assert "MV rebalance" in html
    assert "Target w*" in html
    assert "Synthetic IPS binding matrix" in html
    assert "Advisory bundle" in html
    assert "pm.advise" in html
    assert "axiom checklist" in html
    assert "tax: stub" in html
    assert "not_computed" in html
    assert "attribution.evaluate" in html
    assert "active return vs ex-ante class assumption" in html
    assert "Kill-criteria watch" in html
    assert "Alerts only" in html
    assert "Backtest results" not in html
    assert "Risk manifest" not in html
    assert "Parametric VaR" not in html


def test_catalog_omits_decision_detail() -> None:
    html = render_catalog()
    assert "axiom checklist" not in html
    assert "<h2>Advisory bundle" not in html
    assert "<h2>Synthetic IPS binding matrix</h2>" not in html
    assert "<h2>IPS drift monitor" not in html


def test_api_pages_decision() -> None:
    from warehouse.dashboard.pages.decision import load_decision_page

    data = load_decision_page()
    assert data.phase3.household_id
    assert data.advisory.correlation_id
    assert data.error is None


def test_execution_page_loads() -> None:
    from warehouse.dashboard.pages.execution import render_execution_page

    html = render_execution_page()
    assert "Reconciliation queue" in html
    assert "Daily refresh timeline" in html
    assert "Staged orders" in html
    assert "Solver comparison" in html
    assert "Entity graph" not in html
    assert "Tax scenario panel" not in html
    assert "Audit log stream" not in html


def test_catalog_omits_execution_detail() -> None:
    html = render_catalog()
    assert "<h2>Reconciliation queue</h2>" not in html
    assert "<h2>Staged orders" not in html
    assert "<h2>Solver comparison</h2>" not in html


def test_api_pages_execution() -> None:
    from warehouse.dashboard.pages.execution import load_execution_page

    data = load_execution_page()
    assert data.phase2.household_id
    assert data.error is None


def test_reporting_page_loads() -> None:
    from warehouse.dashboard.pages.reporting import render_reporting_page

    html = render_reporting_page()
    assert "Tax scenario panel" in html
    assert "partial" in html
    assert "Reconciliation queue" not in html
    assert "Staged orders" not in html


def test_catalog_omits_reporting_detail() -> None:
    html = render_catalog()
    assert "<h2>Tax scenario panel</h2>" not in html


def test_api_pages_reporting() -> None:
    from warehouse.dashboard.pages.reporting import load_reporting_page

    data = load_reporting_page()
    assert data.phase4.household_id
    assert data.error is None


def test_infra_page_loads() -> None:
    from warehouse.dashboard.pages.infra import render_infra_page

    html = render_infra_page()
    assert "Infrastructure health" in html
    assert "Audit log stream" in html
    assert "Phase 5 infra (planned)" in html
    assert "Postgres migration status" in html
    assert "Reconciliation queue" not in html


def test_catalog_links_to_infra_detail() -> None:
    html = render_catalog()
    assert 'href="/infra"' in html
    assert "Full infra detail" in html


def test_catalog_includes_orchestrator_gate() -> None:
    html = render_catalog()
    assert "Office Manager gate" in html


def test_api_pages_infra() -> None:
    from warehouse.dashboard.pages.infra import load_infra_page

    data = load_infra_page()
    assert len(data.infra_checks) == 6
    assert data.error is None


def test_catalog_omits_operational_detail() -> None:
    html = render_catalog()
    assert "<h2>Entity graph" not in html
    assert "<h2>Security master</h2>" not in html
    assert "Parametric VaR" not in html
    assert "axiom checklist" not in html
    assert "Phase roadmap" in html
    assert "Dashboard panels" in html


def test_dashboard_redirects_to_catalog() -> None:
    server = HTTPServer(("127.0.0.1", 0), DashboardHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        import urllib.request

        response = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/dashboard",
            timeout=5,
        )
        assert response.geturl().endswith("/")
        assert "Operational planes" in response.read().decode()
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_status_report_includes_all_phases() -> None:
    report = build_status_report()
    assert len(report.phases) == len(PHASES)
    assert report.live_panel_count >= 15
    assert report.infra_error_count == 0
    assert len(report.infra_checks) == 6
    assert len(report.workflows) == 7


def test_render_html_contains_key_sections() -> None:
    html = render_html()
    assert "Infrastructure health" in html
    assert "Entity graph" in html
    assert "Security master" in html
    assert "Schema status" in html
    assert "Ingest status" in html
    assert "Positions" in html and "lots" in html
    assert "Risk manifest" in html
    assert "Level 1" in html
    assert "Parametric VaR" in html
    assert "2008_liquidity" in html
    assert "Audit log stream" in html
    assert "Phase roadmap" in html
    assert "Dashboard panels" in html
    assert "Workflow catalog" in html
    assert "after-tax wealth" in html
    assert "Synthetic IPS binding matrix" in html
    assert "Advisory bundle" in html
    assert "pm.advise" in html
    assert "axiom checklist" in html
    assert "tax: stub" in html
    assert "not_computed" in html
    assert "Office Manager gate" in html
    # pa0: attribution residual panel (5th PM leg).
    assert "attribution.evaluate" in html
    assert "active return vs ex-ante class assumption" in html
    # pa1: kill-criteria watch panel (alerts only, human gate).
    assert "Kill-criteria watch" in html
    assert "Alerts only" in html
    # po0: MV rebalance panel (target weights w*, advisory).
    assert "MV rebalance" in html
    assert "Target w*" in html


def test_optimizer_panel_shows_mu_source_label() -> None:
    """po0 §B.9: panel labels μ as an ex-ante class assumption (PO6)."""
    html = render_html()
    assert "ex-ante class assumption" in html


def test_mu_not_named_forecast() -> None:
    """po0 §B.9: rendered rebalance copy never calls μ a forecast/alpha.

    Scans the rendered panel text — the ``mu_source`` Literal is trivially
    safe by typing, so the real guard is on the copy (mirrors the analyst
    test_residual_not_named_alpha).
    """
    from warehouse.dashboard.optimizer_data import load_optimizer_dashboard
    from warehouse.dashboard.render_phase3 import (
        render_optimizer_rebalance_section,
    )

    panel = render_optimizer_rebalance_section(load_optimizer_dashboard())
    lowered = panel.lower()
    assert "forecast" not in lowered
    assert "alpha" not in lowered
