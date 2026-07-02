"""Catalog page — dashboard entry point (Lib6)."""

from __future__ import annotations

import html

from warehouse.dashboard.layout import (
    infra_badge,
    panel_badge,
    phase_badge,
    readiness_badge,
    wrap_page,
)
from warehouse.dashboard.navigation import (
    live_panel_count,
    page_for_panel,
    plane_pages_for_catalog,
)
from warehouse.dashboard.render_orchestrator import render_orchestrator_section
from warehouse.dashboard.status import StatusReport, build_status_report
from warehouse.orchestrator import recent_in_flight


def render_catalog(report: StatusReport | None = None) -> str:
    report = report or build_status_report()
    body_parts: list[str] = []

    if report.infra_error_count > 0:
        body_parts.append(
            '<section class="error-banner">'
            f"<strong>{report.infra_error_count} infra error(s).</strong> "
            'See <a href="/infra">Infrastructure</a> for detail.'
            "</section>"
        )

    body_parts.append(_metrics_section(report))
    body_parts.append(_plane_cards_section())
    body_parts.append(_phase_roadmap_section(report))
    body_parts.append(_panel_registry_section(report))
    body_parts.append(_infra_summary_section(report))
    body_parts.append(_workflow_section(report))
    body_parts.append(render_orchestrator_section(recent_in_flight(limit=10)))

    subtitle = (
        f"Living status report · v{report.version} · "
        f"{report.app_env} · catalog"
    )
    return wrap_page(
        title="Investment Warehouse — Catalog",
        subtitle=subtitle,
        body="".join(body_parts),
        active_page_id="catalog",
        generated_at=report.generated_at,
        footer_extra=(
            '<a href="/testing">testing matrix</a> · '
            '<a href="/risk">risk build</a>'
        ),
    )


def _metrics_section(report: StatusReport) -> str:
    north = html.escape(report.north_star)
    order = html.escape(report.build_order)
    live = report.live_panel_count
    planned = report.planned_panel_count
    workflows = len(report.workflows)
    planes = len(report.planes)
    errors = report.infra_error_count
    return (
        "<p><strong>Portfolio-management platform</strong> — the living "
        "status report for the daily PM loop: <strong>observe → update → "
        "allocate → check → report</strong> over a book (positions, mandate, "
        "beliefs). Advisory only; the human approval gate dominates.</p>"
        f"<p><strong>North star:</strong> {north} · "
        f"<strong>Build order:</strong> {order}</p>"
        '<div class="metrics">'
        f'<div class="metric"><strong>{live}</strong> live panels</div>'
        f'<div class="metric"><strong>{planned}</strong> planned panels</div>'
        f'<div class="metric"><strong>{workflows}</strong> workflows</div>'
        f'<div class="metric"><strong>{planes}</strong> planes</div>'
        f'<div class="metric"><strong>{errors}</strong> infra errors</div>'
        "</div>"
    )


def _plane_cards_section() -> str:
    plane_cards = []
    for plane, page in plane_pages_for_catalog():
        count = live_panel_count(page)
        plane_cards.append(
            f"""<article class="plane-card">
  <h3><a href="{html.escape(page.path)}">{html.escape(plane.name)}</a></h3>
  <p><code>{html.escape(plane.package)}</code></p>
  <p>{readiness_badge(plane.readiness)} · {count} live panel(s) on page</p>
  <p>{html.escape(plane.note)}</p>
</article>"""
        )
    cards = "".join(plane_cards)
    return (
        "<section><h2>Operational planes</h2>"
        f'<div class="plane-cards">{cards}</div></section>'
    )


def _phase_roadmap_section(report: StatusReport) -> str:
    phase_rows = "".join(
        f"<tr><td>Phase {p.number}</td><td>{html.escape(p.name)}</td>"
        f"<td>{phase_badge(p.status)}</td>"
        f"<td>{html.escape(p.dashboard_summary)}</td></tr>"
        for p in report.phases
    )
    return (
        "<section><h2>Phase roadmap</h2><table>"
        "<thead><tr><th>Phase</th><th>Name</th><th>Status</th>"
        "<th>Dashboard at run</th></tr></thead>"
        f"<tbody>{phase_rows}</tbody></table></section>"
    )


def _panel_registry_section(report: StatusReport) -> str:
    panel_rows = "".join(
        _panel_registry_row(panel.name, panel.phase, panel.status)
        for phase in report.phases
        for panel in phase.panels
    )
    return (
        "<section><h2>Dashboard panels</h2><table>"
        "<thead><tr><th>Panel</th><th>Phase</th><th>Status</th>"
        "<th>Page</th></tr></thead>"
        f"<tbody>{panel_rows}</tbody></table></section>"
    )


def _infra_summary_section(report: StatusReport) -> str:
    infra_rows = "".join(
        f"<tr><td>{html.escape(c.component)}</td>"
        f"<td>{infra_badge(c.status)}</td>"
        f"<td>{html.escape(c.detail)}</td>"
        f"<td>{html.escape(c.error) if c.error else '—'}</td></tr>"
        for c in report.infra_checks
    )
    return (
        "<section><h2>Infrastructure health</h2>"
        '<p><a href="/infra">Full infra detail →</a></p><table>'
        "<thead><tr><th>Component</th><th>Status</th>"
        "<th>Detail</th><th>Error</th></tr></thead>"
        f"<tbody>{infra_rows}</tbody></table></section>"
    )


def _workflow_section(report: StatusReport) -> str:
    workflow_rows = "".join(
        f"<tr><td>{html.escape(w.name)}</td><td>{html.escape(w.owner)}</td>"
        f"<td>{html.escape(', '.join(w.inputs))}</td>"
        f"<td>{html.escape(', '.join(w.outputs))}</td>"
        f"<td>{w.sla_hours or '—'}</td></tr>"
        for w in report.workflows
    )
    return (
        "<section><h2>Workflow catalog</h2><table>"
        "<thead><tr><th>Workflow</th><th>Owner</th><th>Inputs</th>"
        "<th>Outputs</th><th>SLA (h)</th></tr></thead>"
        f"<tbody>{workflow_rows}</tbody></table></section>"
    )


def _panel_registry_row(name: str, phase: int, status: str) -> str:
    page = page_for_panel(name)
    page_link = (
        f'<a href="{html.escape(page.path)}">{html.escape(page.nav_label)}</a>'
    )
    return (
        f"<tr><td>{html.escape(name)}</td><td>Phase {phase}</td>"
        f"<td>{panel_badge(status)}</td><td>{page_link}</td></tr>"
    )
