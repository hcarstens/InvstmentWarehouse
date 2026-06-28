"""Orchestrator gate dashboard HTML — in-flight register (OM8)."""

from __future__ import annotations

import html

from warehouse.orchestrator.models import InFlightRecord


def render_orchestrator_section(records: list[InFlightRecord]) -> str:
    if not records:
        body = "<p>No gate requests recorded yet.</p>"
    else:
        rows = "".join(
            f"<tr><td><code>{html.escape(r.correlation_id)}</code></td>"
            f"<td>{html.escape(r.intent.value)}</td>"
            f"<td>{html.escape(r.household_id)}</td>"
            f"<td>{html.escape(r.assigned_actor or '—')}</td>"
            f"<td>{html.escape(r.stage.value)}</td>"
            f"<td>{r.elapsed_ms if r.elapsed_ms is not None else '—'}</td>"
            f"</tr>"
            for r in records
        )
        body = f"""
    <table>
      <thead>
        <tr>
          <th>correlation_id</th><th>intent</th><th>household</th>
          <th>actor</th><th>stage</th><th>ms</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""

    return f"""
  <section>
    <h2>Office Manager gate</h2>
    <p><span class="badge badge-ok">live</span>
       Single entry · hub-and-spoke dispatch to Portfolio Manager</p>
    {body}
  </section>"""
