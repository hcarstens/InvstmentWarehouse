"""Risk build stakeholder dashboard tests."""

from warehouse.dashboard.risk_build_data import load_risk_build_report
from warehouse.dashboard.server import render_risk_build_html


def test_risk_build_report_has_deliverables() -> None:
    report = load_risk_build_report()
    assert report.contract_status == "v0b"
    assert len(report.deliverables) >= 7
    assert len(report.rungs) == 5
    assert report.shipped_count == 3
    assert any(d.id == "v0a-envelope" for d in report.deliverables)
    assert any(d.id == "v0b-scenarios" for d in report.deliverables)
    assert any(d.track == "hnw_synthetic" for d in report.deliverables)
    v0b = next(d for d in report.deliverables if d.id == "v0b-scenarios")
    assert v0b.status == "shipped"


def test_render_risk_build_html_sections() -> None:
    html = render_risk_build_html()
    assert "Risk &amp; synthetic build tracker" in html
    assert "Deliverables" in html
    assert "Synthetic rung ladder" in html
    assert "Smoke checks" in html
    assert "v0a-envelope" not in html
    assert "evaluate_risk service" in html
    service_check = next(c for c in load_risk_build_report().smoke_checks if c.name == "evaluate_risk service")
    assert service_check.ok
    assert "Level 1" in html
