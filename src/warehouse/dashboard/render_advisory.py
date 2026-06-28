"""Advisory bundle dashboard HTML — PM narrative + specialist legs."""

from __future__ import annotations

import html

from warehouse.dashboard.advisory_data import AdvisoryDashboardData
from warehouse.messaging.payloads import AxiomScore

_AXIOM_LABELS: dict[str, str] = {
    "axiom_1": "Whole book",
    "axiom_2": "Effective bets",
    "axiom_3": "Concentration",
    "axiom_4": "Survive to compound",
    "axiom_5": "Margin of safety",
    "axiom_6": "Control exposure",
    "axiom_7": "Rebalance on evidence",
}

_SCORE_BADGE: dict[AxiomScore, str] = {
    AxiomScore.PASS: "badge-ok",
    AxiomScore.WARN: "badge-warn",
    AxiomScore.BREACH: "badge-error",
    AxiomScore.NOT_COMPUTED: "badge-muted",
}


def _axiom_strip(narrative_axioms: dict[str, AxiomScore]) -> str:
    chips: list[str] = []
    for axiom_id, label in _AXIOM_LABELS.items():
        score = narrative_axioms.get(axiom_id, AxiomScore.NOT_COMPUTED)
        badge = _SCORE_BADGE[score]
        chips.append(
            f'<span class="badge {badge}" title="{html.escape(axiom_id)}">'
            f"{html.escape(label)}: {html.escape(score.value)}</span>"
        )
    return " ".join(chips)


def _specialist_badges(status: dict[str, str]) -> str:
    order = ("risk", "analyst", "optimizer", "tax")
    chips: list[str] = []
    for leg in order:
        state = status.get(leg, "unknown")
        badge = "badge-warn" if state == "stub" else "badge-ok"
        chips.append(
            f'<span class="badge {badge}">{html.escape(leg)}: '
            f"{html.escape(state)}</span>"
        )
    return " ".join(chips)


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
        narrative = bundle.narrative
        axiom_html = ""
        specialist_html = ""
        headline = ""
        if narrative is not None:
            headline = (
                f"<p><strong>{html.escape(narrative.headline)}</strong></p>"
            )
            axiom_html = (
                f"<h3>ℍ_Allocation axiom checklist</h3>"
                f"<p>{_axiom_strip(narrative.axioms_scored)}</p>"
            )
            specialist_html = (
                f"<h3>Specialist legs</h3>"
                f"<p>{_specialist_badges(narrative.specialist_status)}</p>"
            )
        body = f"""
    <p><span class="badge badge-ok">live</span>
       Dispatch via <code>pm.advise</code> ·
       correlation <code>{html.escape(advisory.correlation_id)}</code></p>
    {headline}
    {axiom_html}
    {specialist_html}
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
