"""Risk build stakeholder dashboard tests."""

from warehouse.dashboard.risk_build_data import load_risk_build_report
from warehouse.dashboard.server import render_risk_build_html


def test_risk_build_report_has_deliverables() -> None:
    report = load_risk_build_report()
    assert report.contract_status == "proposed"
    assert len(report.deliverables) >= 7
    assert len(report.rungs) == 5
    assert report.shipped_count == 0
    assert any(d.id == "v0a-envelope" for d in report.deliverables)
    assert any(d.track == "hnw_synthetic" for d in report.deliverables)


def test_render_risk_build_html_sections() -> None:
    html = render_risk_build_html()
    assert "Risk &amp; synthetic build tracker" in html
    assert "Deliverables" in html
    assert "Synthetic rung ladder" in html
    assert "Smoke checks" in html
    assert "v0a-envelope" not in html
    assert "evaluate_risk service" in html
    assert "Level 1" in html
