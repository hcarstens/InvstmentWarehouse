"""Phase 4 dashboard HTML fragments."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from warehouse.dashboard.phase4_data import Phase4DashboardData

if TYPE_CHECKING:
    from warehouse.dashboard.report_writer_data import ReportWriterPanelData
    from warehouse.dashboard.reporting_performance_data import (
        ReportingPerformanceData,
    )


def render_phase4_data_sections(
    phase4: Phase4DashboardData,
    *,
    form_action: str = "/data",
) -> str:
    """Custodian selector + alternatives — data plane page."""
    error = ""
    if phase4.error:
        error = (
            f'<section class="error-banner"><strong>Phase 4 error:</strong> '
            f"{html.escape(phase4.error)}</section>"
        )

    custodian_options = "".join(
        f'<option value="{html.escape(c.custodian_id)}"'
        f"{' selected' if c.custodian_id == phase4.selected_custodian_id else ''}>"
        f"{html.escape(c.name)}</option>"
        for c in phase4.custodians
    )

    pos_rows = "".join(
        f"<tr><td>{html.escape(p.account_name)}</td>"
        f"<td>{html.escape(p.ticker or '—')}</td>"
        f"<td>{p.quantity}</td>"
        f"<td>{p.market_value or '—'}</td></tr>"
        for p in phase4.custodian_positions
    )

    ingest_rows = "".join(
        f"<tr><td>{html.escape(r.run_id)}</td>"
        f"<td>{html.escape(r.file_name)}</td>"
        f"<td>{html.escape(r.status)}</td>"
        f"<td>{r.rows_processed}</td></tr>"
        for r in phase4.custodian_ingest_runs
    )

    alt_rows = "".join(
        f"<tr><td>{html.escape(h.name)}</td>"
        f"<td>{html.escape(h.asset_type)}</td>"
        f"<td>{h.committed_capital:,.0f}</td>"
        f"<td>{h.called_capital:,.0f}</td>"
        f"<td>{h.current_nav:,.0f}</td>"
        f"<td>{h.last_mark_date}</td></tr>"
        for h in phase4.alternative_holdings
    )

    evt_rows = "".join(
        f"<tr><td>{html.escape(e.event_type)}</td>"
        f"<td>{html.escape(e.holding_id)}</td>"
        f"<td>{e.amount:,.0f}</td>"
        f"<td>{e.event_date}</td>"
        f"<td>{html.escape(e.notes)}</td></tr>"
        for e in phase4.alternative_events
    )
    action = html.escape(form_action)
    custodian_id = html.escape(phase4.selected_custodian_id)

    return f"""{error}
  <section>
    <h2>Custodian selector</h2>
    <form class="search" method="get" action="{action}">
      <label>Custodian
        <select name="custodian">{custodian_options}</select>
      </label>
      <button type="submit">Filter</button>
    </form>
    <h3>Positions ({custodian_id})</h3>
    <table>
      <thead><tr><th>Account</th><th>Ticker</th><th>Qty</th><th>Market value</th></tr></thead>
      <tbody>{pos_rows or '<tr><td colspan="4">No positions</td></tr>'}</tbody>
    </table>
    <h3>Ingest runs</h3>
    <table>
      <thead><tr><th>Run</th><th>File</th><th>Status</th><th>Rows</th></tr></thead>
      <tbody>{ingest_rows or '<tr><td colspan="4">No ingest runs</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Alternatives sub-ledger</h2>
    <table>
      <thead><tr><th>Name</th><th>Type</th><th>Committed</th><th>Called</th><th>NAV</th><th>Last mark</th></tr></thead>
      <tbody>{alt_rows or '<tr><td colspan="6">No alternative holdings</td></tr>'}</tbody>
    </table>
    <h3>Events</h3>
    <table>
      <thead><tr><th>Type</th><th>Holding</th><th>Amount</th><th>Date</th><th>Notes</th></tr></thead>
      <tbody>{evt_rows or '<tr><td colspan="5">No events</td></tr>'}</tbody>
    </table>
  </section>"""


def render_phase4_execution_sections(phase4: Phase4DashboardData) -> str:
    """Staged orders + solver comparison — execution plane page."""
    error = ""
    if phase4.error:
        error = (
            f'<section class="error-banner"><strong>Phase 4 error:</strong> '
            f"{html.escape(phase4.error)}</section>"
        )

    order_rows = "".join(
        f"<tr><td>{html.escape(o.order_id)}</td>"
        f"<td>{html.escape(o.approval_request_id)}</td>"
        f"<td>{html.escape(o.side)} {o.quantity} {html.escape(o.security_id)}</td>"
        f"<td>{html.escape(o.status)}</td>"
        f"<td>{o.updated_at.isoformat()}</td></tr>"
        for o in phase4.staged_orders
    )

    cmp_rows = "".join(
        f"<tr><td>{html.escape(c.comparison_id)}</td>"
        f"<td>{c.heuristic_trade_count}</td><td>{c.mip_trade_count}</td>"
        f"<td>{c.heuristic_tax_delta:.2f}</td><td>{c.mip_tax_delta:.2f}</td>"
        f"<td>{c.heuristic_runtime_ms}ms</td><td>{c.mip_runtime_ms}ms</td></tr>"
        for c in phase4.solver_comparisons
    )

    return f"""{error}
  <section>
    <h2>Staged orders — {html.escape(phase4.household_id)}</h2>
    <table>
      <thead><tr><th>Order</th><th>Approval</th><th>Trade</th><th>Status</th><th>Updated</th></tr></thead>
      <tbody>{order_rows or '<tr><td colspan="5">No staged orders</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Solver comparison</h2>
    <table>
      <thead><tr><th>Run</th><th>H trades</th><th>MIP trades</th><th>H tax Δ</th><th>MIP tax Δ</th><th>H ms</th><th>MIP ms</th></tr></thead>
      <tbody>{cmp_rows or '<tr><td colspan="7">No comparisons</td></tr>'}</tbody>
    </table>
  </section>"""


def render_tax_scenario_section(phase4: Phase4DashboardData) -> str:
    """Tax scenario panel — reporting plane page."""
    error = ""
    if phase4.error:
        error = (
            f'<section class="error-banner"><strong>Load error:</strong> '
            f"{html.escape(phase4.error)}</section>"
        )

    tax_rows = "".join(
        f"<tr><td>{html.escape(t.scenario_name)}</td>"
        f"<td>{t.baseline_tax:,.2f}</td>"
        f"<td>{t.scenario_tax:,.2f}</td>"
        f"<td>{t.tax_delta:,.2f}</td>"
        f"<td>{t.created_at.isoformat()}</td></tr>"
        for t in phase4.tax_scenarios
    )

    return f"""{error}
  <section>
    <h2>Tax scenario panel</h2>
    <p><span class="badge badge-warn">partial</span>
       Tax scenarios — reporting-owned compute via
       <code>warehouse.reporting.tax</code>; decision interim estimator unchanged.</p>
    <table>
      <thead><tr><th>Scenario</th><th>Baseline tax</th><th>Scenario tax</th><th>Delta</th><th>Run at</th></tr></thead>
      <tbody>{tax_rows or '<tr><td colspan="5">No tax scenarios</td></tr>'}</tbody>
    </table>
  </section>"""


def render_performance_section(
    perf: ReportingPerformanceData,
) -> str:
    """Household performance panel — reporting plane page."""
    error = ""
    if perf.error:
        error = (
            f'<section class="error-banner"><strong>Performance error:</strong> '
            f"{html.escape(perf.error)}</section>"
        )
    if perf.report is None:
        body = (
            "<p>No performance snapshot — fix errors above.</p>"
            if perf.error
            else "<p>No performance data.</p>"
        )
        return f"""{error}
  <section>
    <h2>Household performance</h2>
    <p><span class="badge badge-live">live</span>
       <code>warehouse.reporting.performance</code></p>
    {body}
  </section>"""

    r = perf.report
    return f"""{error}
  <section>
    <h2>Household performance — {html.escape(perf.household_id)}</h2>
    <p><span class="badge badge-live">live</span>
       as of {html.escape(r.as_of_date)} ·
       <code>build_household_performance_report</code></p>
    <table>
      <thead><tr><th>Total MV</th><th>Unrealized</th><th>Realized YTD</th></tr></thead>
      <tbody><tr>
        <td>{r.total_market_value:,.2f}</td>
        <td>{r.unrealized_gain:,.2f}</td>
        <td>{r.realized_gain_ytd:,.2f}</td>
      </tr></tbody>
    </table>
  </section>"""


def render_report_writer_section(
    data: ReportWriterPanelData,
) -> str:
    """Report writer panel — artifact-backed BLUF preview and paths."""
    if data.panel_status != "live":
        label = (
            "Report writer error"
            if data.panel_status == "error"
            else "Report writer"
        )
        msg = data.error or "Report writer panel unavailable."
        return f"""
  <section>
    <h2>Report writer</h2>
    <section class="error-banner"><strong>{html.escape(label)}:</strong>
      {html.escape(msg)}</section>
    <p><code>warehouse.reporting.report_writer</code> ·
       <code>report.build</code></p>
  </section>"""

    ts = data.generated_at.isoformat() if data.generated_at else "—"
    bluf = html.escape(data.bluf_preview or "—")
    pdf_path = html.escape(data.external_pdf_path or "—")
    sha_preview = html.escape(data.external_pdf_sha256_preview or "—")
    sha_full = html.escape(data.external_pdf_sha256 or "")
    sha_title = f' title="{sha_full}"' if sha_full else ""
    return f"""
  <section>
    <h2>Report writer — {html.escape(data.household_id)}</h2>
    <p><span class="badge badge-live">live</span>
       snapshot <code>{html.escape(data.snapshot_id or "—")}</code> ·
       period <code>{html.escape(data.period_label or "—")}</code> ·
       as of {html.escape(str(data.as_of_date))} ·
       generated {html.escape(ts)}</p>
    <h3>Executive summary (BLUF) — external.md excerpt</h3>
    <blockquote><p>{bluf}</p></blockquote>
    <p><em>Figures in the preview trace to exhibits in
       <code>bundle.json</code> ({html.escape(data.snapshot_id or "")}).</em></p>
    <h3>Artifact paths</h3>
    <ul>
      <li>internal.md — <code>{html.escape(data.internal_markdown_path or "—")}</code></li>
      <li>external.md — <code>{html.escape(data.external_markdown_path or "—")}</code></li>
      <li>external.pdf — <code>{pdf_path}</code>
        · sha256 <code{sha_title}>{sha_preview}</code></li>
      <li>bundle.json — <code>{html.escape(data.bundle_json_path or "—")}</code></li>
    </ul>
    <p><code>warehouse.reporting.report_writer</code> ·
       <code>report.build</code></p>
  </section>"""
