"""Dashboard status report tests."""

from warehouse.dashboard.phases import PHASES
from warehouse.dashboard.server import render_html
from warehouse.dashboard.status import build_status_report


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
