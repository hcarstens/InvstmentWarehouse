"""HTML for the consolidated testing matrix and per-plane QA footnotes."""

from __future__ import annotations

import html

from warehouse.dashboard.layout import badge
from warehouse.dashboard.testing_data import (
    PlaneTestResult,
    TestingReport,
    load_testing_report,
    pyramid_target_mix,
)
from warehouse.dashboard.testing_registry import slice_by_plane_id


def _coverage_cell(plane: PlaneTestResult) -> str:
    if plane.coverage_pct is None:
        return "—"
    pct = f"{plane.coverage_pct:.1f}%"
    if plane.coverage_status == "below_floor":
        floor = f"{plane.coverage_floor_pct:.0f}%"
        return f"{pct} {badge('below floor', 'warn')} (floor {floor})"
    return pct


def _mutation_cell(plane: PlaneTestResult) -> str:
    if plane.mutation_kill_pct is None:
        return "—"
    return f"kill {plane.mutation_kill_pct:.0f}%"


def _status_badge(plane: PlaneTestResult, *, has_report: bool) -> str:
    if not has_report:
        return badge("no report", "muted")
    if not plane.ok:
        return badge("failing", "err")
    return badge("ok", "ok")


def _plane_row(plane: PlaneTestResult, *, has_report: bool) -> str:
    if has_report and plane.tests > 0:
        pass_cell = f"{plane.passed}/{plane.tests}"
        fail_cell = str(plane.failed)
    else:
        pass_cell = "—"
        fail_cell = "—"
    return (
        f"<tr><td>{html.escape(plane.name)}</td>"
        f"<td><code>{html.escape(plane.plane_id)}</code></td>"
        f"<td>{pass_cell}</td>"
        f"<td>{fail_cell}</td>"
        f"<td>{_coverage_cell(plane)}</td>"
        f"<td>{_mutation_cell(plane)}</td>"
        f"<td>{html.escape(plane.risk_tier)}</td>"
        f"<td>{_status_badge(plane, has_report=has_report)}</td></tr>"
    )


def _headline_metrics(report: TestingReport) -> str:
    target = pyramid_target_mix()
    if not report.has_report:
        return (
            '<div class="metrics">'
            '<div class="metric"><strong>—</strong>pass rate</div>'
            '<div class="metric"><strong>—</strong>planes below floor</div>'
            f'<div class="metric"><strong>{target.unit_pct:.0f}/'
            f"{target.integration_pct:.0f}/"
            f"{target.e2e_pct:.0f}</strong>pyramid target %</div>"
            "</div>"
        )

    overall = report.overall
    rate = f"{overall.passed}/{overall.tests}" if overall.tests else "0/0"
    ok_kind = "ok" if overall.ok else "err"
    rate_badge = badge(rate, ok_kind)
    below = overall.planes_below_floor
    below_badge = badge(str(below), "warn" if below else "ok")

    pyramid_bits = "—"
    if report.pyramid is not None:
        actual = report.pyramid
        pyramid_bits = (
            f"actual {actual.unit_pct:.0f}/"
            f"{actual.integration_pct:.0f}/"
            f"{actual.e2e_pct:.0f} · "
            f"target {target.unit_pct:.0f}/"
            f"{target.integration_pct:.0f}/"
            f"{target.e2e_pct:.0f}"
        )

    cov = (
        f"{overall.coverage_pct:.1f}%"
        if overall.coverage_pct is not None
        else "—"
    )
    stale = (
        '<p><span class="badge badge-warn">stale</span> '
        "artifact git SHA differs from HEAD — "
        "run <code>warehouse test report</code></p>"
        if report.stale
        else ""
    )
    return (
        f"{stale}"
        '<div class="metrics">'
        f'<div class="metric">{rate_badge}<span>pass rate</span></div>'
        f'<div class="metric">{below_badge}'
        "<span>planes below floor</span></div>"
        f'<div class="metric"><strong>{cov}</strong>'
        "<span>overall coverage</span></div>"
        f'<div class="metric"><span>{html.escape(pyramid_bits)}</span>'
        "<strong>pyramid</strong></div>"
        "</div>"
    )


def render_testing_matrix(report: TestingReport) -> str:
    """Consolidated testing table for ``/testing``."""
    if not report.has_report:
        banner = (
            '<section class="error-banner" style="background:#fef3c7;'
            'border-color:#fcd34d;color:#92400e">'
            "<strong>No report yet.</strong> Run "
            "<code>warehouse test report</code> to populate this matrix "
            "(st2 CLI — panel flips stub→live when artifact exists)."
            "</section>"
        )
    else:
        ts = (
            report.generated_at.isoformat()
            if report.generated_at
            else "unknown"
        )
        sha = html.escape(report.git_sha or "—")
        banner = (
            f"<p>Report generated <code>{html.escape(ts)}</code> · "
            f"git <code>{sha}</code></p>"
        )

    rows = "".join(
        _plane_row(p, has_report=report.has_report) for p in report.planes
    )
    return f"""
  <section>
    <h2>Testing matrix</h2>
    <p>Per-plane pytest pass/fail and line coverage (ST3: coverage is a
    gap-finder badge — never gates <code>ok</code>). Mutation kill % on
    critical planes is report-only.</p>
    {banner}
    {_headline_metrics(report)}
    <table>
      <tr>
        <th>Plane</th><th>ID</th><th>Pass</th><th>Fail</th>
        <th>Coverage</th><th>Mutation</th><th>Risk</th><th>Status</th>
      </tr>
      {rows}
    </table>
    <p><a href="/api/testing">testing JSON</a></p>
  </section>"""


def render_qa_footnote(
    plane_id: str,
    report: TestingReport | None = None,
) -> str:
    """One-line QA badge for plane page footers (§4.8)."""
    bundle = report or load_testing_report()
    plane = next(
        (p for p in bundle.planes if p.plane_id == plane_id),
        None,
    )
    if plane is None:
        reg = slice_by_plane_id(plane_id)
        if reg is None:
            return ""
        plane = PlaneTestResult(
            plane_id=reg.plane_id,
            name=reg.name,
            coverage_floor_pct=reg.coverage_floor_pct,
            risk_tier=reg.risk_tier,
        )

    link = '<a href="/testing">full matrix →</a>'

    if not bundle.has_report:
        return (
            '<span class="qa-footnote">QA · no report yet — run '
            "<code>warehouse test report</code> · "
            f"{link}</span>"
        )

    if plane.tests == 0:
        pass_line = "no tests run"
    elif plane.failed == 0:
        pass_line = f"✓ {plane.passed}/{plane.tests} passing"
    else:
        pass_line = f"✗ {plane.passed}/{plane.tests} — {plane.failed} failing"

    cov_bits = ""
    if plane.coverage_pct is not None:
        cov = f"{plane.coverage_pct:.1f}%"
        if plane.coverage_status == "below_floor":
            floor = f"{plane.coverage_floor_pct:.0f}%"
            cov_bits = f" · coverage {cov} ⚠ (floor {floor})"
        else:
            cov_bits = f" · coverage {cov}"

    mut_bits = ""
    if plane.mutation_kill_pct is not None:
        mut_bits = f" · mutation kill {plane.mutation_kill_pct:.0f}%"

    stale_bits = ""
    if bundle.stale:
        stale_bits = " · stale — run warehouse test report"

    return (
        f'<span class="qa-footnote">QA · {html.escape(pass_line)}'
        f"{cov_bits}{mut_bits}{stale_bits} · {link}</span>"
    )
