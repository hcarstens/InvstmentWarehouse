"""Phase 2 dashboard HTML fragments."""

from __future__ import annotations

import html
from decimal import Decimal

from warehouse.dashboard.phase2_data import Phase2DashboardData


def _money(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"${value:,.2f}"


def _status_badge(status: str) -> str:
    kind = {"success": "ok", "error": "err", "running": "warn"}.get(status, "muted")
    return f'<span class="badge badge-{kind}">{html.escape(status)}</span>'


def render_phase2_sections(phase2: Phase2DashboardData, *, risk_html: str = "") -> str:
    ingest_rows = "".join(
        f"<tr><td>{html.escape(r.run_id)}</td>"
        f"<td>{html.escape(r.file_name)}</td>"
        f"<td>{_status_badge(r.status)}</td>"
        f"<td>{r.rows_processed}</td>"
        f"<td>{html.escape(r.error_message or '—')}</td></tr>"
        for r in phase2.ingest_runs
    )
    position_rows = "".join(
        f"<tr><td>{html.escape(p.account_name)}</td>"
        f"<td>{html.escape(p.ticker or '—')}</td>"
        f"<td>{p.quantity}</td>"
        f"<td>{_money(p.total_cost_basis)}</td>"
        f"<td>{_money(p.market_value)}</td>"
        f"<td>{_money(p.unrealized_gain)}</td>"
        f"<td>{'yes' if p.is_restricted else 'no'}</td></tr>"
        for p in phase2.positions
    )
    break_rows = "".join(
        f"<tr><td>{html.escape(b.break_id)}</td>"
        f"<td>{html.escape(b.account_id)}</td>"
        f"<td>{html.escape(b.description)}</td>"
        f"<td>{html.escape(b.opened_at.isoformat())}</td>"
        f"<td>{'open' if not b.resolved else 'resolved'}</td></tr>"
        for b in phase2.reconciliation_breaks
    )
    step_rows = "".join(
        f"<tr><td>{html.escape(s.step_name)}</td>"
        f"<td>{_status_badge(s.status)}</td>"
        f"<td>{html.escape(s.detail or '—')}</td>"
        f"<td>{html.escape(s.error_message or '—')}</td></tr>"
        for s in phase2.refresh_steps
    )
    audit_rows = "".join(
        f"<tr><td>{html.escape(a.occurred_at.isoformat())}</td>"
        f"<td>{html.escape(a.actor_id)}</td>"
        f"<td>{html.escape(a.action)}</td>"
        f"<td>{html.escape(a.resource_type)}</td>"
        f"<td>{html.escape(a.resource_id)}</td></tr>"
        for a in phase2.audit_entries
    )
    pnl = phase2.household_pnl
    pnl_summary = ""
    if pnl:
        pnl_summary = (
            f"<p><strong>{html.escape(pnl.household_id)}</strong> · "
            f"as of {pnl.as_of_date} · "
            f"market {_money(pnl.total_market_value)} · "
            f"cost {_money(pnl.total_cost_basis)} · "
            f"unrealized {_money(pnl.unrealized_gain)} · "
            f"{pnl.lot_count} lots</p>"
        )

    error = ""
    if phase2.error:
        error = (
            f'<section class="error-banner"><strong>Phase 2 error:</strong> '
            f"{html.escape(phase2.error)}</section>"
        )

    return f"""{error}
  <section>
    <h2>Ingest status</h2>
    <table>
      <thead><tr><th>Run</th><th>File</th><th>Status</th><th>Rows</th><th>Error</th></tr></thead>
      <tbody>{ingest_rows or '<tr><td colspan="5">No ingest runs</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Positions &amp; lots — {html.escape(phase2.household_id)}</h2>
    {pnl_summary}
    <table>
      <thead><tr><th>Account</th><th>Ticker</th><th>Qty</th><th>Cost</th><th>Market</th><th>Unrealized</th><th>Restricted</th></tr></thead>
      <tbody>{position_rows or '<tr><td colspan="7">No lots</td></tr>'}</tbody>
    </table>
  </section>

{risk_html}

  <section>
    <h2>Reconciliation queue</h2>
    <table>
      <thead><tr><th>Break</th><th>Account</th><th>Description</th><th>Opened</th><th>Status</th></tr></thead>
      <tbody>{break_rows or '<tr><td colspan="5">No open breaks</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Daily refresh timeline</h2>
    <table>
      <thead><tr><th>Step</th><th>Status</th><th>Detail</th><th>Error</th></tr></thead>
      <tbody>{step_rows or '<tr><td colspan="4">No refresh run — use warehouse refresh</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Audit log stream</h2>
    <table>
      <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>ID</th></tr></thead>
      <tbody>{audit_rows or '<tr><td colspan="5">No audit entries</td></tr>'}</tbody>
    </table>
  </section>"""
