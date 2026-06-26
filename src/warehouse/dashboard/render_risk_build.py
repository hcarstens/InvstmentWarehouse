"""HTML for the risk build stakeholder dashboard."""

from __future__ import annotations

import html

from warehouse.dashboard.render_risk import render_risk_section
from warehouse.dashboard.risk_build_data import RiskBuildReport
from warehouse.dashboard.risk_data import RiskDashboardData


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge badge-{kind}">{html.escape(text)}</span>'


def _status_kind(status: str) -> str:
    return {
        "shipped": "ok",
        "in_progress": "warn",
        "planned": "muted",
        "proposed": "muted",
    }.get(status, "muted")


def render_risk_build_page(
    build: RiskBuildReport,
    risk: RiskDashboardData | None = None,
) -> str:
    contract_badge = _badge(
        build.contract_status, _status_kind(build.contract_status)
    )
    deliverable_rows = "".join(
        f"<tr><td>{_badge(d.slice, 'muted')}</td>"
        f"<td>{html.escape(d.name)}</td>"
        f"<td>{_badge(d.status, _status_kind(d.status))}</td>"
        f"<td><code>{html.escape(d.track)}</code></td>"
        f"<td>{html.escape(d.note)}</td></tr>"
        for d in build.deliverables
    )
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
  <p class="sub">Contract {contract_badge} · {build.shipped_count} shipped ·
  {build.planned_count} planned · auto-refresh 60s</p>
  <div class="stats">
    <div class="stat"><strong>North star</strong><br>Standalone risk module —
    <code>evaluate_risk(request, manifest)</code></div>
    <div class="stat"><strong>Update registry</strong><br>
    <code>dashboard/risk_build_registry.py</code> when PRs land</div>
  </div>
  <h2>Deliverables</h2>
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
  <h2>Live risk manifest (demo household)</h2>
  {risk_section}
  <footer><p>Stakeholder view — <code>warehouse serve --risk</code> opens this page.
  Registry drives status; smoke checks verify artifacts exist.</p></footer>
</body>
</html>"""
