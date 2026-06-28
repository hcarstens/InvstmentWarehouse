"""Advisory bundle dashboard HTML — stub panel for ``pm.advise``."""

from __future__ import annotations

import html

from warehouse.dashboard.advisory_data import AdvisoryDashboardData


def render_advisory_section(advisory: AdvisoryDashboardData) -> str:
    error = ""
    if advisory.error:
        error = (
            f'<section class="error-banner"><strong>Advisory error:</strong> '
            f"{html.escape(advisory.error)}</section>"
        )

    bundle = advisory.bundle
    if bundle is None:
        body = "<p>No advisory bundle loaded.</p>"
    else:
        trade_count = len(bundle.proposal.trades)
        drift_alerts = len(bundle.drift.alerts) + len(
            bundle.drift.concentration_alerts
        )
        body = f"""
    <p><span class="badge badge-warn">stub</span>
       Live dispatch via <code>pm.advise</code> ·
       correlation <code>{html.escape(advisory.correlation_id)}</code></p>
    <table>
      <thead><tr><th>Leg</th><th>Summary</th></tr></thead>
      <tbody>
        <tr><td>risk.evaluate</td>
            <td>VaR 95 {bundle.risk.report.level_1_portfolio.parametric_var.value}</td></tr>
        <tr><td>optimizer.propose</td>
            <td>{trade_count} trades · tax delta {bundle.proposal.estimated_tax_delta}</td></tr>
        <tr><td>tax.scenario</td>
            <td>baseline {bundle.tax.baseline_tax} ·
                scenario {bundle.tax.scenario_tax} ·
                delta {bundle.tax.tax_delta}
                <em>(stub — zero until estimate engine ships)</em></td></tr>
        <tr><td>policy.check</td>
            <td>{drift_alerts} drift alert(s)</td></tr>
      </tbody>
    </table>"""

    return f"""
  <section>
    <h2>Advisory bundle (pm.advise)</h2>
    {error}
    {body}
  </section>"""
