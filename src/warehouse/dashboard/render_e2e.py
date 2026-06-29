"""End-to-end smoke matrix panel — cohort × leg pass/fail (synthetic)."""

from __future__ import annotations

import html

from warehouse.dashboard.e2e_data import E2ePanelData


def _leg_badge(ok: bool) -> str:
    if ok:
        return '<span class="badge badge-ok">pass</span>'
    return '<span class="badge badge-err">fail</span>'


def render_e2e_smoke_section(data: E2ePanelData) -> str:
    """E2E smoke matrix from persisted artifact (st4 — no live re-run)."""
    error = ""
    if data.error:
        error = (
            '<section class="error-banner"><strong>End-to-end smoke '
            f"error:</strong> {html.escape(data.error)}</section>"
        )

    if data.panel_status == "empty":
        return """
  <section>
    <h2>End-to-end smoke matrix (synthetic)</h2>
    <p><span class="badge badge-warn">no artifact</span>
       Run <code>warehouse test report</code> to populate the E2E smoke
       matrix (4 cohorts × N legs).</p>
    <p><em>Each row generates one household (positions + IPS) and drives the
       whole stack — policy drift, v0 TLH, optimizer v1 (MV-QP + scenario-robust
       stress), scenario card, and the pm.advise coordinator.</em></p>
  </section>"""

    status_badge = "badge-err" if data.panel_status == "error" else "badge-ok"
    summary_badge = "badge-ok" if data.all_ok else "badge-warn"
    stale_line = ""
    if data.stale:
        stale_line = (
            '<p><span class="badge badge-warn">stale</span> '
            "artifact git SHA differs from HEAD — "
            "run <code>warehouse test report</code></p>"
        )
    ts = data.generated_at.isoformat() if data.generated_at else "unknown"
    sha = html.escape(data.git_sha or "—")

    header_cells = "".join(
        f"<th>{html.escape(name)}</th>" for name in data.leg_names
    )

    body_rows = ""
    for row in data.rows:
        by_leg = {leg.workflow: leg for leg in row.legs}
        leg_cells = ""
        for name in data.leg_names:
            leg = by_leg.get(name)
            if leg is None:
                leg_cells += "<td>—</td>"
            else:
                title = html.escape(leg.detail, quote=True)
                leg_cells += f'<td title="{title}">{_leg_badge(leg.ok)}</td>'
        overall = _leg_badge(row.ok)
        body_rows += (
            f"<tr><td><code>{html.escape(row.cohort_id)}</code></td>"
            f"<td>rung {row.rung}</td><td>seed {row.seed}</td>"
            f"{leg_cells}<td>{overall}</td></tr>"
        )
    if not body_rows:
        span = 4 + len(data.leg_names)
        body_rows = f'<tr><td colspan="{span}">No smoke run</td></tr>'

    return f"""
  <section>
    <h2>End-to-end smoke matrix (synthetic)</h2>
    {error}
    {stale_line}
    <p>Artifact generated <code>{html.escape(ts)}</code> ·
       git <code>{sha}</code></p>
    <p><span class="badge {status_badge}">{html.escape(data.panel_status)}</span>
       <span class="badge {summary_badge}">{data.passed}/{data.households}
       households pass</span> · artifact-backed (no live re-run on page view)</p>
    <p><em>Each row generates one household (positions + IPS) and drives the
       whole stack — policy drift, v0 TLH, optimizer v1 (MV-QP + scenario-robust
       stress), scenario card, and the pm.advise coordinator. Hover a cell for
       leg detail. Proves generation feeds every plane.</em></p>
    <table>
      <thead><tr><th>Cohort</th><th>Rung</th><th>Seed</th>
        {header_cells}<th>Overall</th></tr></thead>
      <tbody>{body_rows}</tbody>
    </table>
  </section>"""
