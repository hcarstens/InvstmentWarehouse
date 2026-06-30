"""Risk build stakeholder dashboard tests."""

from warehouse.dashboard.risk_build_data import load_risk_build_report
from warehouse.dashboard.server import render_risk_build_html


def test_risk_build_report_has_deliverables() -> None:
    report = load_risk_build_report()
    assert report.contract_status == "v1.2"
    assert len(report.deliverables) >= 7
    assert len(report.rungs) == 5
    assert report.shipped_count == 23
    assert report.planned_count == 0
    assert report.synthetic_ips_status == "si4"
    assert len(report.synthetic_ips_deliverables) == 6
    assert report.deliverables[0].track == "synthetic_ips"
    si0a = next(d for d in report.deliverables if d.id == "si0a-asset-class")
    assert si0a.status == "shipped"
    si0b = next(d for d in report.deliverables if d.id == "si0b-ips-fields")
    assert si0b.status == "shipped"
    si1 = next(d for d in report.deliverables if d.id == "si1-emit-ips")
    assert si1.status == "shipped"
    si2 = next(d for d in report.deliverables if d.id == "si2-validate-ips")
    assert si2.status == "shipped"
    si3 = next(d for d in report.deliverables if d.id == "si3-workflow-smoke")
    assert si3.status == "shipped"
    si4 = next(d for d in report.deliverables if d.id == "si4-dashboard-seed")
    assert si4.status == "shipped"
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
    qa2 = next(d for d in report.deliverables if d.id == "qa2-oms-transitions")
    assert qa2.status == "shipped"
    qa5 = next(d for d in report.deliverables if d.id == "qa5-optimizer-edges")
    assert qa5.status == "shipped"


def test_render_risk_build_html_sections() -> None:
    html = render_risk_build_html()
    assert "Risk &amp; synthetic build tracker" in html
    assert "Synthetic IPS implementation" in html
    assert "si0a → si0b → si1" in html
    assert "All deliverables" in html
    assert "Risk asset test suite" in html
    assert "asset-test-busy" in html
    assert "Run Phase B full" in html
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
