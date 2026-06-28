"""Infrastructure dashboard HTML fragments."""

from __future__ import annotations

import html

from warehouse.dashboard.layout import infra_badge, panel_badge
from warehouse.dashboard.phase2_data import Phase2DashboardData
from warehouse.infra.health import InfraCheck


def render_infra_checks_section(checks: list[InfraCheck]) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(c.component)}</td>"
        f"<td>{infra_badge(c.status)}</td>"
        f"<td>{html.escape(c.detail)}</td>"
        f"<td>{html.escape(c.error) if c.error else '—'}</td></tr>"
        for c in checks
    )
    return f"""
  <section>
    <h2>Infrastructure health</h2>
    <table>
      <thead><tr><th>Component</th><th>Status</th><th>Detail</th><th>Error</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </section>"""


def render_audit_log_section(phase2: Phase2DashboardData) -> str:
    audit_rows = "".join(
        f"<tr><td>{html.escape(a.occurred_at.isoformat())}</td>"
        f"<td>{html.escape(a.actor_id)}</td>"
        f"<td>{html.escape(a.action)}</td>"
        f"<td>{html.escape(a.resource_type)}</td>"
        f"<td>{html.escape(a.resource_id)}</td></tr>"
        for a in phase2.audit_entries
    )
    return f"""
  <section>
    <h2>Audit log stream</h2>
    <table>
      <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>ID</th></tr></thead>
      <tbody>{audit_rows or '<tr><td colspan="5">No audit entries</td></tr>'}</tbody>
    </table>
  </section>"""


def render_planned_infra_panels() -> str:
    stubs = (
        ("Postgres migration status", "Phase 5 — docker-compose prod parity"),
        ("Job queue monitor", "Phase 5 — Redis queue not wired in dev"),
        ("Object store health", "Phase 5 — S3-compatible object store"),
    )
    rows = "".join(
        f"<tr><td>{html.escape(name)}</td>"
        f"<td>{panel_badge('planned')}</td>"
        f"<td>{html.escape(note)}</td></tr>"
        for name, note in stubs
    )
    return f"""
  <section>
    <h2>Phase 5 infra (planned)</h2>
    <table>
      <thead><tr><th>Panel</th><th>Status</th><th>Note</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </section>"""
