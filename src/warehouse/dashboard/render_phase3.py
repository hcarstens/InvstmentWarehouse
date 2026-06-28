"""Phase 3 dashboard HTML fragments."""

from __future__ import annotations

import html
from decimal import Decimal

from warehouse.dashboard.optimizer_data import OptimizerPanelData
from warehouse.dashboard.phase3_data import Phase3DashboardData
from warehouse.dashboard.render_synthetic_ips import (
    render_synthetic_ips_section,
)


def _pct(value: Decimal) -> str:
    return f"{value * 100:.1f}%"


def _signed_pct(value: Decimal) -> str:
    return f"{value * 100:+.1f}%"


def render_optimizer_rebalance_section(data: OptimizerPanelData) -> str:
    """po0 MV rebalance panel — target-vs-current w, Δw, RC, illiquid flags.

    Advisory only: w*/Δw are proposals; nothing is staged or executed (human
    gate). μ is labelled an ex-ante class assumption (PO6), never a forecast.
    """
    error = ""
    if data.error:
        error = (
            '<section class="error-banner"><strong>MV rebalance panel '
            f"error:</strong> {html.escape(data.error)}</section>"
        )

    status_badge = "badge-err" if data.panel_status == "error" else "badge-ok"

    def _row(r) -> str:  # type: ignore[no-untyped-def]
        flags = []
        if r.illiquid:
            flags.append(
                '<span class="badge badge-warn">advisory only — not '
                "daily tradable</span>"
            )
        if r.unbounded:
            flags.append('<span class="badge badge-muted">no IPS bound</span>')
        flag_html = " ".join(flags) or "—"
        return (
            f"<tr><td>{html.escape(r.sleeve)}</td>"
            f"<td>{_pct(r.current_weight)}</td>"
            f"<td>{_pct(r.target_weight)}</td>"
            f"<td>{_signed_pct(r.delta_w)}</td>"
            f"<td>{_signed_pct(r.policy_drift)}</td>"
            f"<td>{_pct(r.risk_contribution)}</td>"
            f"<td>{flag_html}</td></tr>"
        )

    rows = "".join(_row(r) for r in data.rows) or (
        '<tr><td colspan="7">No rebalance computed</td></tr>'
    )
    binding = ", ".join(data.binding_bounds) or "none"
    return f"""
  <section>
    <h2>MV rebalance (target weights w*)</h2>
    {error}
    <p><span class="badge {status_badge}">{html.escape(data.panel_status)}</span>
       Cohort <code>{html.escape(data.cohort_id)}</code> ·
       household <code>{html.escape(data.household_id)}</code> ·
       as of {data.as_of_date.isoformat()} ·
       config <code>{html.escape(data.config_version)}</code></p>
    <p>μ source: <strong>{html.escape(data.mu_source_label)}</strong>
       (base-regime Σ only) · risk aversion λ = {data.lam} ·
       turnover ‖Δw‖₁ = {_pct(data.turnover_l1)} ·
       objective = {data.objective_value}</p>
    <p>Binding IPS bounds at w*: {html.escape(binding)}</p>
    <p><em>Advisory only — w*/Δw are proposals; the constrained MV QP stages
       no trade and executes nothing (human gate). Weight ≠ risk: read RC.</em></p>
    <table>
      <thead><tr><th>Sleeve</th><th>Current</th><th>Target w*</th>
        <th>Δw</th><th>Policy drift</th><th>RC</th><th>Flags</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </section>"""


def render_phase3_sections(phase3: Phase3DashboardData) -> str:
    error = ""
    if phase3.error:
        error = (
            f'<section class="error-banner"><strong>Phase 3 error:</strong> '
            f"{html.escape(phase3.error)}</section>"
        )

    drift_rows = ""
    alert_rows = ""
    if phase3.ips_drift:
        drift_rows = "".join(
            f"<tr><td>{html.escape(r.asset_class)}</td>"
            f"<td>{_pct(r.current_weight)}</td>"
            f"<td>{_pct(r.target_weight)}</td>"
            f"<td>{_pct(r.drift)}</td></tr>"
            for r in phase3.ips_drift.rows
        )
        alerts = (
            phase3.ips_drift.alerts + phase3.ips_drift.concentration_alerts
        )
        alert_rows = (
            "".join(f"<li>{html.escape(a)}</li>" for a in alerts)
            or "<li>No alerts</li>"
        )

    opt = phase3.optimization_runs[0] if phase3.optimization_runs else None
    trade_rows = ""
    if opt:
        trade_rows = "".join(
            f"<tr><td>{html.escape(t.side)}</td>"
            f"<td>{html.escape(t.lot_id or '—')}</td>"
            f"<td>{html.escape(t.security_id)}</td>"
            f"<td>{t.quantity}</td>"
            f"<td>{html.escape(t.rationale)}</td></tr>"
            for t in opt.trades
        )
    binding = ", ".join(opt.binding_constraints) if opt else "—"
    tax_delta = opt.estimated_tax_delta if opt else "—"

    approval_rows = "".join(
        f"<tr><td>{html.escape(a.request_id)}</td>"
        f"<td>{html.escape(a.status)}</td>"
        f"<td>{html.escape(a.reviewer_id or '—')}</td>"
        f"<td>{a.reviewed_at.isoformat() if a.reviewed_at else '—'}</td></tr>"
        for a in phase3.approval_requests
    )

    backtest_rows = "".join(
        f"<tr><td>{html.escape(b.run_id)}</td>"
        f"<td>{b.start_date}</td><td>{b.end_date}</td>"
        f"<td>{b.after_tax_return:.4f}</td>"
        f"<td>{b.tax_delta:.4f}</td>"
        f"<td><code>{html.escape(b.config_hash)}</code></td>"
        f"<td>{html.escape(b.input_snapshot_id)}</td></tr>"
        for b in phase3.backtest_runs
    )

    constraint_rows = "".join(
        f"<tr><td>{html.escape(c)}</td><td>active</td></tr>"
        for c in phase3.active_constraints
    )

    synthetic_ips_html = ""
    if phase3.synthetic_ips is not None:
        synthetic_ips_html = render_synthetic_ips_section(phase3.synthetic_ips)

    return f"""{error}
  <section>
    <h2>IPS drift monitor — {html.escape(phase3.household_id)}</h2>
    <table>
      <thead><tr><th>Asset class</th><th>Current</th><th>Target</th><th>Drift</th></tr></thead>
      <tbody>{drift_rows or '<tr><td colspan="4">No IPS data</td></tr>'}</tbody>
    </table>
    <ul>{alert_rows}</ul>
  </section>

  <section>
    <h2>Optimizer proposals</h2>
    <p>Latest run tax delta: <strong>{html.escape(str(tax_delta))}</strong> · Binding: {html.escape(binding)}</p>
    <table>
      <thead><tr><th>Side</th><th>Lot</th><th>Security</th><th>Qty</th><th>Rationale</th></tr></thead>
      <tbody>{trade_rows or '<tr><td colspan="5">No trades proposed</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Approval queue</h2>
    <table>
      <thead><tr><th>Request</th><th>Status</th><th>Reviewer</th><th>Reviewed</th></tr></thead>
      <tbody>{approval_rows or '<tr><td colspan="4">No approval requests</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Backtest results</h2>
    <table>
      <thead><tr><th>Run</th><th>Start</th><th>End</th><th>After-tax</th><th>Tax delta</th><th>Config</th><th>Snapshot</th></tr></thead>
      <tbody>{backtest_rows or '<tr><td colspan="7">No backtests</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Constraint binding report</h2>
    <table>
      <thead><tr><th>Constraint</th><th>State</th></tr></thead>
      <tbody>{constraint_rows or '<tr><td colspan="2">No constraints loaded</td></tr>'}</tbody>
    </table>
  </section>
{synthetic_ips_html}"""
