"""Risk build stakeholder dashboard tests."""

from warehouse.dashboard.risk_build_data import load_risk_build_report
from warehouse.dashboard.server import render_risk_build_html


def test_risk_build_report_has_deliverables() -> None:
    report = load_risk_build_report()
    assert report.contract_status == "v1.2"
    assert len(report.deliverables) >= 7
    assert len(report.rungs) == 5
    assert report.shipped_count == 11
    hnw = next(d for d in report.deliverables if d.id == "hnw-generator")
    assert hnw.status == "shipped"
    phase_a = next(
        d for d in report.deliverables if d.id == "asset-test-phase-a"
    )
    assert phase_a.status == "shipped"
    phase_b = next(
        d for d in report.deliverables if d.id == "asset-test-phase-b"
    )
    assert phase_b.status == "shipped"


def test_render_risk_build_html_sections() -> None:
    html = render_risk_build_html()
    assert "Risk &amp; synthetic build tracker" in html
    assert "Deliverables" in html
    assert "Risk asset test suite" in html
    assert "Phase A" in html
    assert "asset-test-phase-a" not in html
    assert "Synthetic rung ladder" in html
    assert "Smoke checks" in html
    assert "v0a-envelope" not in html
    assert "evaluate_risk service" in html
    service_check = next(
        c
        for c in load_risk_build_report().smoke_checks
        if c.name == "evaluate_risk service"
    )
    assert service_check.ok
    assert "Level 1" in html
