"""Daily Movements panel render (pv2) — FIIJ regime + z-scores + attribution.

Faithful, self-contained map (Cartography): it SHOWS z-scores / conditional
vol / regime / the FIIJ signal→view mapping, and it LABELS the omission — the
sleeve-level disclosure states on-screen that name dispersion is not expressed
(§11 A.3). The factor attribution leg renders ``not_computed``, never a fake
zero. Advisory only — these are observations, not orders.
"""

from __future__ import annotations

import html
from decimal import Decimal

from warehouse.dashboard.stats_data import DailyMovementsData


def _pct(value: Decimal) -> str:
    return f"{value * 100:.2f}%"


def _signed_pct(value: Decimal) -> str:
    return f"{value * 100:+.2f}%"


def render_daily_movements_section(data: DailyMovementsData) -> str:
    """Daily Movements — the pv2 FIIJ ingest + daily statistics, on real
    engine output."""
    error = ""
    if data.error:
        error = (
            '<section class="error-banner"><strong>Daily Movements panel '
            f"error:</strong> {html.escape(data.error)}</section>"
        )

    status_badge = "badge-err" if data.panel_status == "error" else "badge-ok"

    def _move_row(m) -> str:  # type: ignore[no-untyped-def]
        badge = "badge-warn" if m.significant else "badge-muted"
        flag = "significant" if m.significant else "noise"
        return (
            f"<tr><td>{html.escape(m.ticker)}</td>"
            f"<td>{_signed_pct(m.ret)}</td>"
            f"<td>{_pct(m.ewma_vol)}</td>"
            f"<td>{m.zscore}</td>"
            f'<td><span class="badge {badge}">{flag}</span></td></tr>'
        )

    move_rows = "".join(_move_row(m) for m in data.moves) or (
        '<tr><td colspan="5">No securities with a return series</td></tr>'
    )

    def _view_row(v) -> str:  # type: ignore[no-untyped-def]
        return (
            f"<tr><td>{html.escape(v.sleeve)}</td>"
            f"<td><code>{html.escape(v.source_ref)}</code></td>"
            f"<td>{_signed_pct(v.expected_excess)}</td>"
            f"<td>{v.confidence}</td>"
            f"<td>{html.escape(v.calibration)}</td></tr>"
        )

    view_rows = "".join(_view_row(v) for v in data.fiij_views) or (
        '<tr><td colspan="5">No active FIIJ signals</td></tr>'
    )

    def _attr_row(a) -> str:  # type: ignore[no-untyped-def]
        return (
            f"<tr><td>{html.escape(a.ticker)}</td>"
            f"<td>{_signed_pct(a.total_return)}</td>"
            f"<td>{_signed_pct(a.active_return)}</td>"
            f"<td>{html.escape(a.active_annualized)}</td></tr>"
        )

    attr_rows = "".join(_attr_row(a) for a in data.attribution) or (
        '<tr><td colspan="4">No positions scored</td></tr>'
    )

    limitations = "".join(
        f"<li>{html.escape(item)}</li>" for item in data.limitations
    )

    return f"""
  <section>
    <h2>Daily Movements (FIIJ ingest + daily statistics)</h2>
    {error}
    <p><span class="badge {status_badge}">{html.escape(data.panel_status)}</span>
       Cohort <code>{html.escape(data.cohort_id)}</code> ·
       household <code>{html.escape(data.household_id)}</code> ·
       as of {data.as_of_date.isoformat()}</p>
    <p>FIIJ regime:
       <span class="badge badge-muted">{html.escape(data.regime_label)}</span>
       (<code>{html.escape(data.regime_class)}</code>) ·
       stats config <code>{html.escape(data.stats_config_version)}</code> ·
       FIIJ config <code>{html.escape(data.fiij_config_version)}</code></p>
    <p class="error-banner"><strong>Altitude:</strong>
       {html.escape(data.disclosure)}</p>
    <h3>Significant moves (z-score vs conditional distribution)</h3>
    <table>
      <thead><tr><th>Security</th><th>Return</th><th>EWMA vol</th>
        <th>z-score</th><th>Move</th></tr></thead>
      <tbody>{move_rows}</tbody>
    </table>
    <p><em>Rolling correlation (¬PS2 watch):</em>
       {html.escape(data.rolling_corr_note)}</p>
    <h3>FIIJ signal → view mapping (sleeve-level)</h3>
    <table>
      <thead><tr><th>Sleeve</th><th>FIIJ signal</th><th>Expected excess</th>
        <th>Confidence</th><th>Calibration (OOS Brier)</th></tr></thead>
      <tbody>{view_rows}</tbody>
    </table>
    <h3>Position P&amp;L attribution (factor leg not_computed)</h3>
    <table>
      <thead><tr><th>Ticker</th><th>Window return</th>
        <th>Active vs class</th><th>Annualized (factor)</th></tr></thead>
      <tbody>{attr_rows}</tbody>
    </table>
    <ul>{limitations}</ul>
  </section>"""
