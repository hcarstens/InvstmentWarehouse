"""Risk manifest dashboard panel — unit hierarchy Levels 1–4."""

from __future__ import annotations

import html
from collections.abc import Callable
from decimal import Decimal

from warehouse.dashboard.risk_data import RiskDashboardData
from warehouse.research.risk.models import PortfolioRiskReport, RiskMetric


def _pct(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.2f}%"


def _num(value: Decimal | None, places: int = 4) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{places}f}"


def _money(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"${float(value):,.0f}"


def _metric_meta(label: str, metric: RiskMetric) -> str:
    parts = [label, f"<code>{html.escape(metric.unit_type.value)}</code>"]
    if metric.confidence is not None:
        parts.append(f"α={html.escape(str(metric.confidence))}")
    if metric.horizon_years is not None:
        parts.append(f"h={html.escape(str(metric.horizon_years))}y")
    if metric.window_days is not None:
        parts.append(f"window={metric.window_days}d")
    if metric.method:
        parts.append(html.escape(metric.method))
    return " · ".join(parts)


def render_risk_section(risk: RiskDashboardData) -> str:
    if risk.error:
        return f"""  <section>
    <h2>Risk manifest — {html.escape(risk.household_id)}</h2>
    <p class="error-banner"><strong>Risk panel error:</strong> {html.escape(risk.error)}</p>
  </section>"""

    report = risk.report
    if report is None:
        return f"""  <section>
    <h2>Risk manifest — {html.escape(risk.household_id)}</h2>
    <p>No risk report available.</p>
  </section>"""

    return _render_report(risk, report)


def _render_report(risk: RiskDashboardData, report: PortfolioRiskReport) -> str:
    l1 = report.level_1_portfolio
    summary = (
        f"<p><strong>Horizon {html.escape(str(risk.horizon_years))}y</strong> · "
        f"model {html.escape(report.model_version)} · "
        f"fingerprint <code>{html.escape(report.input_fingerprint)}</code> · "
        f"source {html.escape(risk.source)} · "
        f"window {report.manifest.vol_window_days}d · "
        f"stress {html.escape(report.manifest.stress_pack_version)}</p>"
    )
    if risk.notional_usd:
        summary += f"<p>Notional {_money(risk.notional_usd)} — dollar tail units enabled.</p>"

    level1_rows = "".join(
        [
            _level1_row("Annualized σ", l1.annualized_volatility, _pct),
            _level1_row("Horizon σ", l1.horizon_volatility, _pct),
            _level1_row("Expected return (h)", l1.expected_return, _pct),
            _level1_row("Parametric VaR", l1.parametric_var, _pct),
            _level1_row("Parametric ES", l1.parametric_es, _pct),
            _level1_row("σ confidence low", l1.confidence_low, _pct),
            _level1_row("σ confidence high", l1.confidence_high, _pct),
        ]
    )
    if l1.dollar_var:
        level1_rows += _level1_row("Dollar VaR", l1.dollar_var, _money)
    if l1.dollar_es:
        level1_rows += _level1_row("Dollar ES", l1.dollar_es, _money)

    class_rows = "".join(
        f"<tr><td>{html.escape(c.asset_class)}</td>"
        f"<td>{_pct(c.weight)}</td>"
        f"<td>{_pct(c.pct_variance_contribution)}</td>"
        f"<td>{_pct(c.annual_volatility)}</td>"
        f"<td>{html.escape(c.measurement.value)}</td>"
        f"<td>{c.liquidity_tier}</td></tr>"
        for c in report.level_2_contributions.by_class
    )
    duration_rows = "".join(
        f"<tr><td>{html.escape(d.bucket)}</td>"
        f"<td>{_pct(d.weight)}</td>"
        f"<td>{_pct(d.pct_variance_contribution)}</td>"
        f"<td>{html.escape(str(d.avg_duration_years)) if d.avg_duration_years else '—'}</td>"
        f"<td>{_num(d.horizon_mismatch, 2)}</td></tr>"
        for d in report.level_2_contributions.by_duration
    )
    sensitivity_rows = "".join(
        f"<tr><td>{html.escape(s.asset_class)}</td>"
        f"<td>{html.escape(s.native_unit.value)}</td>"
        f"<td>{_num(s.value.value, 2)}</td>"
        f"<td>{html.escape(s.measurement.value)}</td></tr>"
        for s in report.level_3_sensitivities.by_sleeve
    )
    stress_rows = "".join(
        f"<tr><td>{html.escape(s.name)}</td>"
        f"<td>{_pct(s.portfolio_return.value)}</td>"
        f"<td>{_money(s.dollar_pnl.value) if s.dollar_pnl else '—'}</td></tr>"
        for s in report.level_4_stress.scenarios
    )
    liquidity_rows = "".join(
        f"<tr><td>{t.tier}</td>"
        f"<td>{_pct(t.weight)}</td>"
        f"<td>{_num(t.days_to_liquidate.value, 0)} days</td></tr>"
        for t in report.liquidity.by_tier
    )
    meas = report.measurement_summary
    meas_line = (
        f"Measurable {_pct(meas.measurable_weight)} · "
        f"Fermi {_pct(meas.fermi_weight)} · "
        f"Fermi share {_pct(meas.fermi_risk_share)}"
    )
    liq_days = _num(report.liquidity.weighted_days.value, 0)

    return f"""  <section>
    <h2>Risk manifest — {html.escape(risk.household_id)}</h2>
    <p class="subtitle">L1–L4 unit hierarchy and liquidity-time (see research docs)</p>
    {summary}
    <p><em>{html.escape(report.aggregation_note)}</em></p>

    <h3>Level 1 — portfolio tail (σ, VaR, ES)</h3>
    <table>
      <thead><tr><th>Metric</th><th>Value</th><th>Disclosure</th></tr></thead>
      <tbody>{level1_rows}</tbody>
    </table>

    <h3>Level 2 — risk contributions (% portfolio variance)</h3>
    <h4>By asset class</h4>
    <table>
      <thead><tr><th>Class</th><th>Weight</th><th>% var</th>
        <th>Annual σ</th><th>Meas</th><th>Tier</th></tr></thead>
      <tbody>{class_rows}</tbody>
    </table>
    <h4>By duration bucket</h4>
    <table>
      <thead><tr><th>Bucket</th><th>Weight</th><th>% var</th>
        <th>Avg dur</th><th>Mismatch</th></tr></thead>
      <tbody>{duration_rows or '<tr><td colspan="5">No duration buckets</td></tr>'}</tbody>
    </table>

    <h3>Level 3 — native sensitivities</h3>
    <table>
      <thead><tr><th>Class</th><th>Unit</th><th>Value</th><th>Measurement</th></tr></thead>
      <tbody>{sensitivity_rows}</tbody>
    </table>

    <h3>Level 4 — named stress replay</h3>
    <table>
      <thead><tr><th>Scenario</th><th>Portfolio return</th><th>Dollar P&amp;L</th></tr></thead>
      <tbody>{stress_rows}</tbody>
    </table>

    <h3>Liquidity-time</h3>
    <p>Weighted days to liquidate: <strong>{liq_days} days</strong></p>
    <table>
      <thead><tr><th>Tier</th><th>Weight</th><th>Days</th></tr></thead>
      <tbody>{liquidity_rows}</tbody>
    </table>

    <p>{meas_line}</p>
    <p><a href="/api/risk">Risk API schema</a> · POST evaluate with fingerprinted inputs</p>
  </section>"""


def _level1_row(
    label: str,
    metric: RiskMetric,
    fmt: Callable[[Decimal], str],
) -> str:
    return (
        f"<tr><td>{html.escape(label)}</td>"
        f"<td>{html.escape(fmt(metric.value))}</td>"
        f"<td>{_metric_meta(label, metric)}</td></tr>"
    )
