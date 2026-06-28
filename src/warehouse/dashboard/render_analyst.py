"""Portfolio Analyst dashboard HTML — kill-criteria watch (pa1).

A distinct analyst panel (separate from the advisory bundle): it surfaces
pre-committed kill-criteria breaches as ADVISORY ALERTS. Nothing here stages or
sells — the advisor decides (CLAUDE.md human gate). pa2 will add the NPA panel
to this module.
"""

from __future__ import annotations

import html

from warehouse.dashboard.analyst_data import KillCriteriaWatchData

_CHECKPOINT_BADGE: dict[str, str] = {
    "pass": "badge-ok",
    "warn": "badge-warn",
    "breach": "badge-err",
    "not_computed": "badge-muted",
    "not_documented": "badge-muted",
}


def _breach_rows(data: KillCriteriaWatchData) -> str:
    if not data.breaches:
        return (
            '<tr><td colspan="5">No kill-criteria breaches — all documented '
            "positions within their pre-committed limits.</td></tr>"
        )
    return "".join(
        f"<tr><td>{html.escape(b.instrument)}</td>"
        f"<td><code>{html.escape(b.account_id)}</code></td>"
        f"<td>{html.escape(b.criterion.value)}</td>"
        f"<td>{b.observed}</td><td>{b.threshold}</td></tr>"
        for b in data.breaches
    )


def render_analyst_section(data: KillCriteriaWatchData) -> str:
    error = ""
    if data.error:
        error = (
            '<section class="error-banner"><strong>Kill-criteria watch '
            f"error:</strong> {html.escape(data.error)}</section>"
        )

    badge = _CHECKPOINT_BADGE.get(data.checkpoint_1, "badge-muted")
    status_badge = "badge-err" if data.panel_status == "error" else "badge-ok"
    return f"""
  <section>
    <h2>Kill-criteria watch</h2>
    {error}
    <p><span class="badge {status_badge}">{html.escape(data.panel_status)}</span>
       Cohort <code>{html.escape(data.cohort_id)}</code> ·
       household <code>{html.escape(data.household_id)}</code> ·
       as of {data.as_of_date.isoformat()}</p>
    <p>{data.thesis_count} pre-committed theses ·
       {data.documented_positions} documented position(s) ·
       checkpoint 1
       <span class="badge {badge}">{html.escape(data.checkpoint_1)}</span></p>
    <p><em>Alerts only — a breach never stages or sells (human gate). The
       advisor decides.</em></p>
    <table>
      <thead><tr><th>Instrument</th><th>Account</th><th>Kill criterion</th>
        <th>Observed</th><th>Threshold</th></tr></thead>
      <tbody>{_breach_rows(data)}</tbody>
    </table>
  </section>"""
