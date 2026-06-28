"""Phase 1 dashboard HTML — entity graph, securities, schema."""

from __future__ import annotations

import html

from warehouse.dashboard.layout import badge
from warehouse.dashboard.phase1_data import Phase1DashboardData


def render_phase1_sections(
    phase1: Phase1DashboardData,
    *,
    form_action: str = "/data",
) -> str:
    error_banner = ""
    if phase1.error:
        error_banner = (
            f'<section class="error-banner"><strong>Data load error:</strong> '
            f"{html.escape(phase1.error)}</section>"
        )

    entity_rows = "".join(
        f"<tr><td>{html.escape(e.entity_id)}</td>"
        f"<td>{html.escape(e.entity_type.value)}</td>"
        f"<td>{html.escape(e.name)}</td>"
        f"<td>{html.escape(e.household_id or '—')}</td></tr>"
        for e in phase1.entity_graph.entities
    )
    relationship_rows = "".join(
        f"<tr><td>{html.escape(r.source_id)}</td>"
        f"<td>{html.escape(r.relationship_type.value)}</td>"
        f"<td>{html.escape(r.target_id)}</td></tr>"
        for r in phase1.entity_graph.relationships
    )
    security_rows = "".join(
        f"<tr><td>{html.escape(s.ticker or '—')}</td>"
        f"<td>{html.escape(s.name)}</td>"
        f"<td>{html.escape(s.asset_class.value)}</td>"
        f"<td>{html.escape(s.tax_character.value)}</td>"
        f"<td>{html.escape(s.wash_sale_substitute_group or '—')}</td></tr>"
        for s in phase1.securities
    )
    schema = phase1.schema_status
    schema_revision = (
        badge("current", "ok")
        if schema.is_current
        else badge("pending", "warn")
    )
    schema_rows = "".join(
        f"<tr><td>{html.escape(t.name)}</td><td>{t.row_count}</td></tr>"
        for t in schema.tables
    )
    q_value = html.escape(phase1.security_query or "")
    action = html.escape(form_action)
    schema_error = ""
    if schema.error:
        schema_error = (
            f'<p class="error-banner">{html.escape(schema.error)}</p>'
        )
    last_applied = (
        schema.last_applied_at.isoformat() if schema.last_applied_at else "—"
    )
    head_revision = html.escape(schema.head_revision)
    current_revision = html.escape(schema.current_revision or "none")
    household_id = html.escape(phase1.household_id)

    return f"""{error_banner}
  <section>
    <h2>Entity graph — {household_id}</h2>
    <h3>Entities</h3>
    <table>
      <thead><tr><th>ID</th><th>Type</th><th>Name</th><th>Household</th></tr></thead>
      <tbody>{entity_rows or '<tr><td colspan="4">No entities</td></tr>'}</tbody>
    </table>
    <h3>Relationships</h3>
    <table>
      <thead><tr><th>Source</th><th>Edge</th><th>Target</th></tr></thead>
      <tbody>{relationship_rows or '<tr><td colspan="3">No relationships</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Security master</h2>
    <form class="search" method="get" action="{action}">
      <label>Search <input type="search" name="q" value="{q_value}" placeholder="ticker, name, CUSIP"></label>
      <button type="submit">Filter</button>
    </form>
    <table>
      <thead><tr><th>Ticker</th><th>Name</th><th>Asset class</th><th>Tax character</th><th>Wash-sale group</th></tr></thead>
      <tbody>{security_rows or '<tr><td colspan="5">No securities</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Schema status</h2>
    <p>Revision: <code>{current_revision}</code> / {head_revision} {schema_revision}</p>
    <p>Last applied: {last_applied}</p>
    {schema_error}
    <table>
      <thead><tr><th>Table</th><th>Rows</th></tr></thead>
      <tbody>{schema_rows or '<tr><td colspan="2">No tables — run warehouse db bootstrap</td></tr>'}</tbody>
    </table>
  </section>"""
