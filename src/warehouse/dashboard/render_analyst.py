"""Portfolio Analyst dashboard HTML — kill-criteria watch + NPA flags.

Two distinct analyst panels (separate from the advisory bundle): the pa1
kill-criteria watch and the pa2 non-performing-asset panel. Both surface
pre-committed/reason-coded breaches as ADVISORY ALERTS — nothing here stages or
sells, and NPA flags never become optimizer constraints; the advisor decides
(CLAUDE.md human gate).
"""

from __future__ import annotations

import html

from warehouse.dashboard.analyst_data import KillCriteriaWatchData
from warehouse.dashboard.npa_data import NpaPanelData

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


_NPA_BADGE: dict[str, str] = {
    "position": "badge-warn",
    "alternative": "badge-warn",
    "manifest": "badge-err",
}


def _npa_rows(data: NpaPanelData) -> str:
    if not data.flags:
        return (
            '<tr><td colspan="5">No non-performing-asset flags — positions '
            "and alternatives within thresholds.</td></tr>"
        )
    rows = []
    for f in data.flags:
        badge = _NPA_BADGE.get(f.subject.value, "badge-muted")
        rows.append(
            f'<tr><td><span class="badge {badge}">'
            f"{html.escape(f.subject.value)}</span></td>"
            f"<td>{html.escape(f.label)}</td>"
            f"<td>{html.escape(f.reason.value)}</td>"
            f"<td>{html.escape(f.detail)}</td>"
            f"<td><code>{html.escape(f.subject_id)}</code></td></tr>"
        )
    return "".join(rows)


def render_npa_section(data: NpaPanelData) -> str:
    error = ""
    if data.error:
        error = (
            '<section class="error-banner"><strong>NPA panel error:'
            f"</strong> {html.escape(data.error)}</section>"
        )

    status_badge = "badge-err" if data.panel_status == "error" else "badge-ok"
    return f"""
  <section>
    <h2>Non-performing-asset flags</h2>
    {error}
    <p><span class="badge {status_badge}">{html.escape(data.panel_status)}</span>
       Cohort <code>{html.escape(data.cohort_id)}</code> ·
       household <code>{html.escape(data.household_id)}</code> ·
       as of {data.as_of_date.isoformat()} ·
       config <code>{html.escape(data.config_version)}</code></p>
    <p>{data.position_count} position(s) · {data.alt_count} alternative(s) ·
       {len(data.flags)} flag(s)</p>
    <p><em>Advisory only — flags feed the approval gate, never optimizer
       constraints or staged trades (human gate). The advisor decides.</em></p>
    <table>
      <thead><tr><th>Subject</th><th>Asset</th><th>Reason</th>
        <th>Detail</th><th>Id</th></tr></thead>
      <tbody>{_npa_rows(data)}</tbody>
    </table>
  </section>"""
