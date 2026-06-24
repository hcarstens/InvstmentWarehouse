"""Dashboard status report tests."""

from warehouse.dashboard.phases import PHASES
from warehouse.dashboard.server import render_html
from warehouse.dashboard.status import build_status_report


def test_status_report_includes_all_phases() -> None:
    report = build_status_report()
    assert len(report.phases) == len(PHASES)
    assert report.live_panel_count >= 5
    assert report.infra_error_count == 0
    assert len(report.infra_checks) == 5
    assert len(report.workflows) == 6


def test_render_html_contains_key_sections() -> None:
    html = render_html()
    assert "Infrastructure health" in html
    assert "Phase roadmap" in html
    assert "Dashboard panels" in html
    assert "Workflow catalog" in html
    assert "after-tax wealth" in html
