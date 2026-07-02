"""Belief Journal panel render (pv1) — prior μ → views → posterior μ → w*.

Advisory only: the posterior μ feeds the po0 QP (a caller change), but the
rebalance is a proposal — nothing is staged or executed (human gate). Views are
labelled by source (``manual`` in pv1) and their calibration is
``not_computed`` — demo is never dressed as a scored forecast.
"""

from __future__ import annotations

import html
from decimal import Decimal

from warehouse.dashboard.beliefs_data import BeliefJournalData


def _pct(value: Decimal) -> str:
    return f"{value * 100:.2f}%"


def _signed_pct(value: Decimal) -> str:
    return f"{value * 100:+.2f}%"


def render_beliefs_journal_section(data: BeliefJournalData) -> str:
    """Belief Journal — the pv1 Bayesian update, on real engine output."""
    error = ""
    if data.error:
        error = (
            '<section class="error-banner"><strong>Belief Journal panel '
            f"error:</strong> {html.escape(data.error)}</section>"
        )

    status_badge = "badge-err" if data.panel_status == "error" else "badge-ok"

    def _view_row(v) -> str:  # type: ignore[no-untyped-def]
        return (
            f"<tr><td>{html.escape(v.sleeve)}</td>"
            f"<td>{_signed_pct(v.expected_excess)}</td>"
            f"<td>{v.confidence}</td>"
            f'<td><span class="badge badge-muted">'
            f"{html.escape(v.source)}</span></td>"
            f"<td>{html.escape(v.calibration)}</td>"
            f"<td>{html.escape(v.rationale)}</td></tr>"
        )

    view_rows = "".join(_view_row(v) for v in data.views) or (
        '<tr><td colspan="6">No views — posterior μ == prior μ '
        "(zero-view identity)</td></tr>"
    )

    def _mu_row(r) -> str:  # type: ignore[no-untyped-def]
        return (
            f"<tr><td>{html.escape(r.sleeve)}</td>"
            f"<td>{_pct(r.prior_mu)}</td>"
            f"<td>{_pct(r.posterior_mu)}</td>"
            f"<td>{_signed_pct(r.mu_delta)}</td>"
            f"<td>{_pct(r.baseline_weight)}</td>"
            f"<td>{_pct(r.posterior_weight)}</td>"
            f"<td>{_signed_pct(r.weight_delta)}</td></tr>"
        )

    mu_rows = "".join(_mu_row(r) for r in data.rows) or (
        '<tr><td colspan="7">No belief update computed</td></tr>'
    )

    return f"""
  <section>
    <h2>Belief Journal (Black–Litterman posterior)</h2>
    {error}
    <p><span class="badge {status_badge}">{html.escape(data.panel_status)}</span>
       Cohort <code>{html.escape(data.cohort_id)}</code> ·
       household <code>{html.escape(data.household_id)}</code> ·
       as of {data.as_of_date.isoformat()} ·
       trace <code>{html.escape(data.correlation_id)}</code></p>
    <p>method: <strong>{html.escape(data.method)}</strong> · τ = {data.tau} ·
       prior source: <strong>{html.escape(data.prior_source_label)}</strong>
       (<code>{html.escape(data.prior_source)}</code>,
       assumptions <code>{html.escape(data.assumptions_version)}</code>) ·
       belief config <code>{html.escape(data.belief_config_version)}</code> ·
       calibration <code>{html.escape(data.calibration)}</code></p>
    <p><em>Advisory only — the posterior μ feeds the po0 QP as its μ input (a
       caller change; the QP is untouched), producing a proposed w*; nothing is
       staged or executed (human gate). Views are demo/<code>manual</code> in
       pv1 (FIIJ signal ingest is pv2); their calibration is
       <code>not_computed</code> until a scored history exists. The prior is an
       ex-ante class assumption, not a reverse-optimized equilibrium.</em></p>
    <h3>Views</h3>
    <table>
      <thead><tr><th>Sleeve</th><th>Expected excess</th><th>Confidence</th>
        <th>Source</th><th>Calibration</th><th>Rationale</th></tr></thead>
      <tbody>{view_rows}</tbody>
    </table>
    <h3>Prior μ → Posterior μ → resulting w* (vs pre-view w*)</h3>
    <table>
      <thead><tr><th>Sleeve</th><th>Prior μ</th><th>Posterior μ</th>
        <th>μ shift</th><th>Pre-view w*</th><th>Posterior w*</th>
        <th>w* shift</th></tr></thead>
      <tbody>{mu_rows}</tbody>
    </table>
  </section>"""
