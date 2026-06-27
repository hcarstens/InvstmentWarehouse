"""Synthetic IPS binding matrix — Phase 3 dashboard HTML."""

from __future__ import annotations

import html

from warehouse.dashboard.synthetic_ips_data import (
    SyntheticIpsDashboardData,
    SyntheticIpsMatrixRow,
)


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge badge-{kind}">{html.escape(text)}</span>'


def render_synthetic_ips_section(data: SyntheticIpsDashboardData) -> str:
    if data.error:
        return (
            '<section class="error-banner">'
            "<strong>Synthetic IPS matrix error:</strong> "
            f"{html.escape(data.error)}</section>"
        )

    def _row(r: SyntheticIpsMatrixRow) -> str:
        bind_kind = "ok" if r.binding_count else "warn"
        val_kind = "ok" if r.validation_ok else "err"
        smoke_kind = "ok" if r.smoke_ok else "err"
        constraints = html.escape(", ".join(r.binding_constraints) or "—")
        return (
            f"<tr><td>{html.escape(r.cohort_id)}</td>"
            f"<td>{r.rung}</td>"
            f"<td><code>{html.escape(r.ips_id)}</code></td>"
            f"<td>{_badge(str(r.binding_count), bind_kind)}</td>"
            f"<td>{constraints}</td>"
            f"<td>{_badge('ok' if r.validation_ok else 'fail', val_kind)}</td>"
            f"<td>{_badge('ok' if r.smoke_ok else 'fail', smoke_kind)}</td>"
            f"</tr>"
        )

    rows = "".join(_row(r) for r in data.rows)
    return f"""
  <section>
    <h2>Synthetic IPS binding matrix</h2>
    <p>Cohort × binding status from in-process emit + workflow smoke
    (seed={data.matrix_seed}, generated {data.generated_at.isoformat()}).</p>
    <table>
      <thead><tr>
        <th>Cohort</th><th>Rung</th><th>IPS id</th><th>Bindings</th>
        <th>Constraints</th><th>Validate</th><th>Smoke</th>
      </tr></thead>
      <tbody>{rows or '<tr><td colspan="7">No rows</td></tr>'}</tbody>
    </table>
  </section>"""
