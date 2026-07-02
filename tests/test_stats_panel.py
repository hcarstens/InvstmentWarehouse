"""Daily Movements panel (pv2) — thin loader over real engine output.

The panel is a thin consumer (M4): it renders the FIIJ ingest + stats engine
output and MUST disclose the sleeve-level altitude on-screen (§11 A.3 — name
dispersion not expressed). Pins: live status, a significant move present, the
factor leg shown as not_computed, and the disclosure in the rendered HTML.
"""

from __future__ import annotations

from warehouse.dashboard.render_stats import render_daily_movements_section
from warehouse.dashboard.stats_data import (
    SLEEVE_LEVEL_DISCLOSURE,
    load_daily_movements_dashboard,
)


def test_panel_loads_live_with_fiij_and_moves() -> None:
    data = load_daily_movements_dashboard()
    assert data.panel_status == "live", data.error
    assert data.regime_class == "neutral"
    assert data.fiij_views, "expected FIIJ signal→view rows"
    assert any(m.significant for m in data.moves), (
        "expected a significant move"
    )
    # Factor leg is honest — attribution annualized renders not_computed.
    assert all(a.active_annualized == "not_computed" for a in data.attribution)


def test_panel_discloses_sleeve_level_altitude() -> None:
    data = load_daily_movements_dashboard()
    assert "name dispersion not expressed" in data.disclosure
    html = render_daily_movements_section(data)
    assert "name dispersion not expressed" in html
    assert "z-score" in html
    assert SLEEVE_LEVEL_DISCLOSURE[:30] in html
