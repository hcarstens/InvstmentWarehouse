"""HTML for the risk build stakeholder dashboard."""

from __future__ import annotations

import html

from warehouse.dashboard.render_risk import render_risk_section
from warehouse.dashboard.risk_build_data import RiskBuildReport
from warehouse.dashboard.risk_build_registry import BuildDeliverable
from warehouse.dashboard.risk_data import RiskDashboardData
from warehouse.research.synthetic.asset_test_suite import (
    AssetTestSuiteResult,
    load_asset_test_summary,
)


def _asset_test_summary_rows(suite: AssetTestSuiteResult | None) -> str:
    if suite is None:
        return "<tr><td colspan='4'><em>No run yet — use API link below</em></td></tr>"
    rows = "".join(
        f"<tr><td>{html.escape(', '.join(c.types))}</td>"
        f"<td>{html.escape(c.status)}</td>"
        f"<td><code>{html.escape(c.fingerprint or '—')}</code></td>"
        f"<td><code>{html.escape(c.report_path or '—')}</code></td></tr>"
        for c in suite.cells[:8]
    )
    extra = ""
    if len(suite.cells) > 8:
        extra = (
            f"<tr><td colspan='4'><em>… {len(suite.cells) - 8} more cells "
            f"(see API JSON)</em></td></tr>"
        )
    return rows + extra


def _asset_test_stats(suite: AssetTestSuiteResult | None, phase: str) -> str:
    if suite is None:
        return f"Phase {phase}: not run"
    parts = ", ".join(f"{k}={v}" for k, v in sorted(suite.summary.items()))
    return (
        f"Phase {phase}: {suite.cells_run} cells · {parts} · "
        f"<code>{html.escape(suite.reports_dir)}</code>"
    )


def render_asset_test_section() -> str:
    phase_a = load_asset_test_summary("A")
    phase_b = load_asset_test_summary("B")
    return f"""
  <h2>Risk asset test suite</h2>
  <p>Walk HNW leaf types through <code>evaluate_risk</code>; per-cell JSON under
  <code>runs/research/risk_asset_tests/</code>.</p>
  <p>{_asset_test_stats(phase_a, "A")}</p>
  <p>{_asset_test_stats(phase_b, "B")}</p>
  <p>
    <a href="/api/risk/asset-tests?phase=a">Run Phase A (JSON)</a> ·
    <a href="/api/risk/asset-tests?phase=b&amp;max_size=2">Run Phase B pairs (JSON)</a> ·
    <a href="/api/risk/asset-tests?phase=b"
       onclick="document.documentElement.classList.add('asset-test-busy')"
       title="32,752 cells — wait cursor until JSON response">Run Phase B full (JSON)</a>
  </p>
  <h3>Phase A — last run (sample)</h3>
  <table>
    <tr><th>Types</th><th>Status</th><th>Fingerprint</th><th>Report</th></tr>
    {_asset_test_summary_rows(phase_a)}
  </table>
"""


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge badge-{kind}">{html.escape(text)}</span>'


def _status_kind(status: str) -> str:
    return {
        "shipped": "ok",
        "in_progress": "warn",
        "planned": "muted",
        "proposed": "muted",
    }.get(status, "muted")


def _deliverable_rows(deliverables: list[BuildDeliverable]) -> str:
    return "".join(
        f"<tr><td>{_badge(d.slice, 'muted')}</td>"
        f"<td>{html.escape(d.name)}</td>"
        f"<td>{_badge(d.status, _status_kind(d.status))}</td>"
        f"<td><code>{html.escape(d.track)}</code></td>"
        f"<td>{html.escape(d.note)}</td></tr>"
        for d in deliverables
    )


def render_risk_build_page(
    build: RiskBuildReport,
    risk: RiskDashboardData | None = None,
) -> str:
    contract_badge = _badge(
        build.contract_status, _status_kind(build.contract_status)
    )
    ips_badge = _badge(
        build.synthetic_ips_status,
        _status_kind(
            "shipped"
            if build.synthetic_ips_status.startswith("si")
            and "next" not in build.synthetic_ips_status
            else "planned"
        ),
    )
    synthetic_ips_rows = _deliverable_rows(build.synthetic_ips_deliverables)
    deliverable_rows = _deliverable_rows(build.deliverables)
    rung_rows = "".join(
        f"<tr><td>{r.rung}</td>"
        f"<td><code>{html.escape(r.owner)}</code></td>"
        f"<td>{_badge(r.status, _status_kind(r.status))}</td>"
        f"<td>{html.escape(r.cohort)}</td>"
        f"<td>{html.escape(r.exercises)}</td></tr>"
        for r in build.rungs
    )
    doc_rows = "".join(
        f'<li><a href="/{html.escape(href)}">{html.escape(label)}</a></li>'
        for label, href in build.doc_links
    )
    smoke_rows = "".join(
        f"<tr><td>{html.escape(c.name)}</td>"
        f"<td>{_badge('ok' if c.ok else 'missing', 'ok' if c.ok else 'err')}</td>"
        f"<td>{html.escape(c.detail)}</td></tr>"
        for c in build.smoke_checks
    )
    risk_section = ""
    if risk is not None:
        risk_section = render_risk_section(risk)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="60">
  <title>Risk build tracker — Investment Warehouse</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; line-height: 1.45; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .sub {{ color: #555; margin-top: 0; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; }}
    th {{ background: #f4f4f4; }}
    .badge {{ padding: 0.15rem 0.45rem; border-radius: 4px; font-size: 0.85rem; }}
    .badge-ok {{ background: #d4edda; }}
    .badge-warn {{ background: #fff3cd; }}
    .badge-muted {{ background: #e9ecef; }}
    .badge-err {{ background: #f8d7da; }}
    nav a {{ margin-right: 1rem; }}
    .stats {{ display: flex; gap: 1.5rem; margin: 1rem 0; }}
    .stat {{ padding: 0.75rem 1rem; background: #f8f9fa; border-radius: 6px; }}
    html.asset-test-busy,
    html.asset-test-busy * {{
      cursor: wait !important;
    }}
  </style>
</head>
<body>
  <nav>
    <a href="/">← Full platform dashboard</a>
    <a href="/api/risk/build">build JSON</a>
    <a href="/api/risk">risk API schema</a>
    <a href="/api/status">status JSON</a>
  </nav>
  <h1>Risk &amp; synthetic build tracker</h1>
  <p class="sub">Risk contract {contract_badge} · Synthetic IPS {ips_badge} ·
  {build.shipped_count} shipped · {build.planned_count} planned · auto-refresh 60s</p>
  <div class="stats">
    <div class="stat"><strong>North star</strong><br>Standalone risk module —
    <code>evaluate_risk(request, manifest)</code></div>
    <div class="stat"><strong>Synthetic IPS</strong><br>
    Paired Shape B + IPS — caller composes risk + drift</div>
    <div class="stat"><strong>Update registry</strong><br>
    <code>dashboard/risk_build_registry.py</code> when PRs land</div>
  </div>
  <h2>Synthetic IPS implementation</h2>
  <p class="sub">Plan: <a href="/docs/synthetic_ips_implementation.md">synthetic_ips_implementation.md</a>
  · Design: <a href="/docs/research/synthetic_ips.md">synthetic_ips.md</a></p>
  <p><code>{html.escape(build.synthetic_ips_pipeline)}</code></p>
  <table>
    <tr><th>Slice</th><th>Name</th><th>Status</th><th>Track</th><th>Note</th></tr>
    {synthetic_ips_rows}
  </table>
  <h2>All deliverables</h2>
  <table>
    <tr><th>Slice</th><th>Name</th><th>Status</th><th>Track</th><th>Note</th></tr>
    {deliverable_rows}
  </table>
  <h2>Synthetic rung ladder</h2>
  <table>
    <tr><th>Rung</th><th>Owner</th><th>Status</th><th>Cohort</th><th>Exercises</th></tr>
    {rung_rows}
  </table>
  <h2>Smoke checks (code on disk)</h2>
  <table>
    <tr><th>Check</th><th>State</th><th>Detail</th></tr>
    {smoke_rows}
  </table>
  <h2>Docs</h2>
  <ul>{doc_rows}</ul>
  {render_asset_test_section()}
  <h2>Live risk manifest (demo household)</h2>
  {risk_section}
  <footer><p>Stakeholder view — <code>warehouse serve --risk</code> opens this page.
  Registry drives status; smoke checks verify artifacts exist.</p></footer>
</body>
</html>"""
