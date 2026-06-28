"""Minimal HTTP dashboard — living status report."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlparse

from warehouse.config import repo_root
from warehouse.dashboard.advisory_data import load_advisory_dashboard
from warehouse.dashboard.analyst_data import load_kill_criteria_dashboard
from warehouse.dashboard.catalog import render_catalog
from warehouse.dashboard.npa_data import load_npa_dashboard
from warehouse.dashboard.optimizer_data import load_optimizer_dashboard
from warehouse.dashboard.pages.data import load_data_page, render_data_page
from warehouse.dashboard.pages.research import (
    load_research_page,
    render_research_page,
)
from warehouse.dashboard.phase1_data import load_phase1_dashboard
from warehouse.dashboard.phase2_data import load_phase2_dashboard
from warehouse.dashboard.phase3_data import load_phase3_dashboard
from warehouse.dashboard.phase4_data import load_phase4_dashboard
from warehouse.dashboard.render_advisory import render_advisory_section
from warehouse.dashboard.render_analyst import (
    render_analyst_section,
    render_npa_section,
)
from warehouse.dashboard.render_orchestrator import render_orchestrator_section
from warehouse.dashboard.render_phase2 import render_phase2_sections
from warehouse.dashboard.render_phase3 import (
    render_optimizer_rebalance_section,
    render_phase3_sections,
)
from warehouse.dashboard.render_phase4 import render_phase4_sections
from warehouse.dashboard.render_risk import render_risk_section
from warehouse.dashboard.render_risk_build import render_risk_build_page
from warehouse.dashboard.risk_build_data import load_risk_build_report
from warehouse.dashboard.risk_data import load_risk_dashboard
from warehouse.dashboard.status import build_status_report


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge badge-{kind}">{html.escape(text)}</span>'


def _readiness_kind(readiness: str) -> str:
    return {"live": "ok", "partial": "warn", "stub": "muted"}.get(
        readiness, "muted"
    )


def _phase_kind(status: str) -> str:
    return {"complete": "ok", "in_progress": "warn", "planned": "muted"}.get(
        status, "muted"
    )


def _panel_kind(status: str) -> str:
    return {"live": "ok", "stub": "warn", "planned": "muted"}.get(
        status, "muted"
    )


def _infra_kind(status: str) -> str:
    return {
        "ok": "ok",
        "skipped": "muted",
        "warn": "warn",
        "error": "err",
    }.get(status, "muted")


def _security_query_from_path(path: str) -> str | None:
    query = parse_qs(urlparse(path).query).get("q", [])
    return query[0] if query else None


def _custodian_from_path(path: str) -> str | None:
    query = parse_qs(urlparse(path).query).get("custodian", [])
    return query[0] if query else None


def render_risk_build_html(*, include_live_manifest: bool = True) -> str:
    build = load_risk_build_report()
    risk = load_risk_dashboard() if include_live_manifest else None
    return render_risk_build_page(build, risk)


def _safe_docs_path(url_path: str) -> Path | None:
    if not url_path.startswith("/docs/"):
        return None
    rel = url_path[len("/docs/") :]
    if ".." in rel or rel.startswith("/"):
        return None
    root = (repo_root() / "docs").resolve()
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def render_html(
    security_query: str | None = None,
    custodian_id: str | None = None,
) -> str:
    report = build_status_report()
    phase1 = load_phase1_dashboard(security_query=security_query)
    phase2 = load_phase2_dashboard()
    risk = load_risk_dashboard(household_id=phase2.household_id)
    phase3 = load_phase3_dashboard()
    phase4 = load_phase4_dashboard(custodian_id=custodian_id)
    advisory = load_advisory_dashboard(household_id=phase2.household_id)
    phase_rows = "".join(
        f"<tr><td>Phase {p.number}</td><td>{html.escape(p.name)}</td>"
        f"<td>{_badge(p.status, _phase_kind(p.status))}</td>"
        f"<td>{html.escape(p.dashboard_summary)}</td></tr>"
        for p in report.phases
    )
    panel_rows = "".join(
        f"<tr><td>{html.escape(panel.name)}</td><td>Phase {panel.phase}</td>"
        f"<td>{_badge(panel.status, _panel_kind(panel.status))}</td></tr>"
        for phase in report.phases
        for panel in phase.panels
    )
    plane_rows = "".join(
        f"<tr><td>{html.escape(p.name)}</td><td><code>{html.escape(p.package)}</code></td>"
        f"<td>{_badge(p.readiness, _readiness_kind(p.readiness))}</td>"
        f"<td>{html.escape(p.note)}</td></tr>"
        for p in report.planes
    )
    workflow_rows = "".join(
        f"<tr><td>{html.escape(w.name)}</td><td>{html.escape(w.owner)}</td>"
        f"<td>{html.escape(', '.join(w.inputs))}</td>"
        f"<td>{html.escape(', '.join(w.outputs))}</td>"
        f"<td>{w.sla_hours or '—'}</td></tr>"
        for w in report.workflows
    )
    infra_rows = "".join(
        f"<tr><td>{html.escape(c.component)}</td>"
        f"<td>{_badge(c.status, _infra_kind(c.status))}</td>"
        f"<td>{html.escape(c.detail)}</td>"
        f"<td>{html.escape(c.error) if c.error else '—'}</td></tr>"
        for c in report.infra_checks
    )
    error_banner = ""
    if phase1.error:
        error_banner = (
            f'<section class="error-banner"><strong>Data load error:</strong> '
            f"{html.escape(phase1.error)}</section>"
        )
    entity_rows = "".join(
        f"<tr><td>{html.escape(e.entity_id)}</td>"
        f"<td>{html.escape(e.entity_type.value)}</td>"
        f"<td>{html.escape(e.name)}</td>"
        f"<td>{html.escape(e.household_id or '—')}</td></tr>"
        for e in phase1.entity_graph.entities
    )
    relationship_rows = "".join(
        f"<tr><td>{html.escape(r.source_id)}</td>"
        f"<td>{html.escape(r.relationship_type.value)}</td>"
        f"<td>{html.escape(r.target_id)}</td></tr>"
        for r in phase1.entity_graph.relationships
    )
    security_rows = "".join(
        f"<tr><td>{html.escape(s.ticker or '—')}</td>"
        f"<td>{html.escape(s.name)}</td>"
        f"<td>{html.escape(s.asset_class.value)}</td>"
        f"<td>{html.escape(s.tax_character.value)}</td>"
        f"<td>{html.escape(s.wash_sale_substitute_group or '—')}</td></tr>"
        for s in phase1.securities
    )
    schema = phase1.schema_status
    schema_revision = (
        _badge("current", "ok")
        if schema.is_current
        else _badge("pending", "warn")
    )
    schema_rows = "".join(
        f"<tr><td>{html.escape(t.name)}</td><td>{t.row_count}</td></tr>"
        for t in schema.tables
    )
    q_value = html.escape(phase1.security_query or "")
    phase2_html = render_phase2_sections(
        phase2, risk_html=render_risk_section(risk)
    )
    phase3_html = render_phase3_sections(phase3)
    optimizer_html = render_optimizer_rebalance_section(
        load_optimizer_dashboard()
    )
    phase4_html = render_phase4_sections(phase4)
    advisory_html = render_advisory_section(advisory)
    analyst_html = render_analyst_section(load_kill_criteria_dashboard())
    npa_html = render_npa_section(load_npa_dashboard())
    orchestrator_html = render_orchestrator_section(advisory.in_flight)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="30">
  <title>Investment Warehouse — Status</title>
  <style>
    :root {{ font-family: system-ui, sans-serif; color: #1a1a1a; background: #f6f7f9; }}
    body {{ max-width: 1100px; margin: 0 auto; padding: 1.5rem; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .subtitle {{ color: #555; margin-top: 0; }}
    .metrics {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }}
    .metric {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.25rem; min-width: 140px; }}
    .metric strong {{ display: block; font-size: 1.5rem; }}
    section {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.25rem; margin: 1rem 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    th, td {{ text-align: left; padding: 0.45rem 0.5rem; border-bottom: 1px solid #eee; vertical-align: top; }}
    th {{ color: #444; }}
    code {{ font-size: 0.85em; }}
    .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }}
    .badge-ok {{ background: #d1fae5; color: #065f46; }}
    .badge-warn {{ background: #fef3c7; color: #92400e; }}
    .badge-muted {{ background: #e5e7eb; color: #374151; }}
    .badge-err {{ background: #fee2e2; color: #991b1b; }}
    .error-banner {{ background: #fee2e2; border: 1px solid #fca5a5; color: #991b1b; padding: 0.75rem 1rem; border-radius: 8px; margin: 1rem 0; }}
    .search {{ margin-bottom: 0.75rem; }}
    footer {{ color: #666; font-size: 0.85rem; margin-top: 1.5rem; }}
  </style>
</head>
<body>
  <h1>Investment Warehouse</h1>
  <p class="subtitle">Living status report · v{html.escape(report.version)} · {html.escape(report.app_env)}</p>
  <p><strong>North star:</strong> {html.escape(report.north_star)} · <strong>Build order:</strong> {html.escape(report.build_order)}</p>
  {error_banner}

  <div class="metrics">
    <div class="metric"><strong>{report.live_panel_count}</strong> live panels</div>
    <div class="metric"><strong>{report.planned_panel_count}</strong> planned panels</div>
    <div class="metric"><strong>{len(report.workflows)}</strong> workflows</div>
    <div class="metric"><strong>{len(report.planes)}</strong> planes</div>
    <div class="metric"><strong>{report.infra_error_count}</strong> infra errors</div>
  </div>

  <section>
    <h2>Infrastructure health</h2>
    <table>
      <thead><tr><th>Component</th><th>Status</th><th>Detail</th><th>Error</th></tr></thead>
      <tbody>{infra_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>Entity graph — {html.escape(phase1.household_id)}</h2>
    <h3>Entities</h3>
    <table>
      <thead><tr><th>ID</th><th>Type</th><th>Name</th><th>Household</th></tr></thead>
      <tbody>{entity_rows or '<tr><td colspan="4">No entities</td></tr>'}</tbody>
    </table>
    <h3>Relationships</h3>
    <table>
      <thead><tr><th>Source</th><th>Edge</th><th>Target</th></tr></thead>
      <tbody>{relationship_rows or '<tr><td colspan="3">No relationships</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Security master</h2>
    <form class="search" method="get" action="/">
      <label>Search <input type="search" name="q" value="{q_value}" placeholder="ticker, name, CUSIP"></label>
      <button type="submit">Filter</button>
    </form>
    <table>
      <thead><tr><th>Ticker</th><th>Name</th><th>Asset class</th><th>Tax character</th><th>Wash-sale group</th></tr></thead>
      <tbody>{security_rows or '<tr><td colspan="5">No securities</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Schema status</h2>
    <p>Revision: <code>{html.escape(schema.current_revision or "none")}</code> / {html.escape(schema.head_revision)} {schema_revision}</p>
    <p>Last applied: {schema.last_applied_at.isoformat() if schema.last_applied_at else "—"}</p>
    {f'<p class="error-banner">{html.escape(schema.error)}</p>' if schema.error else ""}
    <table>
      <thead><tr><th>Table</th><th>Rows</th></tr></thead>
      <tbody>{schema_rows or '<tr><td colspan="2">No tables — run warehouse db bootstrap</td></tr>'}</tbody>
    </table>
  </section>

{phase2_html}

{phase3_html}

{optimizer_html}

{advisory_html}
{analyst_html}
{npa_html}
{orchestrator_html}

{phase4_html}

  <section>
    <h2>Phase roadmap</h2>
    <table>
      <thead><tr><th>Phase</th><th>Name</th><th>Status</th><th>Dashboard at run</th></tr></thead>
      <tbody>{phase_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>Dashboard panels</h2>
    <table>
      <thead><tr><th>Panel</th><th>Phase</th><th>Status</th></tr></thead>
      <tbody>{panel_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>Operational planes</h2>
    <table>
      <thead><tr><th>Plane</th><th>Package</th><th>Readiness</th><th>Note</th></tr></thead>
      <tbody>{plane_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>Workflow catalog</h2>
    <table>
      <thead><tr><th>Workflow</th><th>Owner</th><th>Inputs</th><th>Outputs</th><th>SLA (h)</th></tr></thead>
      <tbody>{workflow_rows}</tbody>
    </table>
  </section>

  <footer>Generated {report.generated_at.isoformat()} · auto-refresh 30s · <a href="/risk">risk build</a> · <a href="/api/status">status</a> · <a href="/api/health">health</a> · <a href="/api/risk">risk API</a> · <a href="/api/phase1">phase1</a> · <a href="/api/phase2">phase2</a> · <a href="/api/phase3">phase3</a> · <a href="/api/phase4">phase4</a></footer>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    risk_landing: bool = False

    def do_GET(self) -> None:
        path_only = self.path.split("?")[0]
        if path_only in ("/risk", "/risk/"):
            body = render_risk_build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        doc_path = _safe_docs_path(path_only)
        if doc_path is not None:
            body = doc_path.read_text(encoding="utf-8").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path_only == "/dashboard":
            self.send_response(301)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if path_only == "/":
            if self.risk_landing:
                body = render_risk_build_html().encode()
            else:
                body = render_catalog().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path_only == "/data":
            body = render_data_page(
                security_query=_security_query_from_path(self.path),
                custodian_id=_custodian_from_path(self.path),
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path_only == "/research":
            body = render_research_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        elif path_only == "/api/pages/research":
            data = load_research_page()
            body = data.model_dump_json(indent=2).encode()
            self.send_response(200 if not data.error else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        elif path_only == "/api/pages/data":
            data = load_data_page(
                security_query=_security_query_from_path(self.path),
                custodian_id=_custodian_from_path(self.path),
            )
            body = data.model_dump_json(indent=2).encode()
            self.send_response(200 if not data.error else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        elif self.path.startswith("/api/phase4"):
            custodian = _custodian_from_path(self.path)
            phase4 = load_phase4_dashboard(custodian_id=custodian)
            body = phase4.model_dump_json(indent=2).encode()
            self.send_response(200 if not phase4.error else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/phase3"):
            phase3 = load_phase3_dashboard()
            body = phase3.model_dump_json(indent=2).encode()
            self.send_response(200 if not phase3.error else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/phase2"):
            phase2 = load_phase2_dashboard()
            body = phase2.model_dump_json(indent=2).encode()
            self.send_response(200 if not phase2.error else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/phase1"):
            phase1 = load_phase1_dashboard(
                security_query=_security_query_from_path(self.path)
            )
            body = phase1.model_dump_json(indent=2).encode()
            self.send_response(200 if not phase1.error else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/health":
            from warehouse.infra.health import run_infra_checks

            checks = run_infra_checks()
            body = json.dumps(
                [c.model_dump() for c in checks], indent=2
            ).encode()
            has_error = any(c.status == "error" for c in checks)
            self.send_response(503 if has_error else 200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path_only == "/api/risk/asset-tests":
            from warehouse.research.synthetic.asset_test_suite import (
                AssetTestPhase,
                run_asset_test_suite,
            )

            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            phase_raw = (qs.get("phase") or ["a"])[0].strip().upper()
            if phase_raw not in ("A", "B"):
                body = json.dumps({"error": "phase must be a or b"}).encode()
                self.send_response(400)
            else:
                phase = cast(AssetTestPhase, phase_raw)
                max_size_raw = qs.get("max_size")
                phase_b_max_size = (
                    int(max_size_raw[0])
                    if max_size_raw and phase == "B"
                    else None
                )
                suite = run_asset_test_suite(
                    phase,
                    phase_b_max_size=phase_b_max_size,
                )
                body = suite.model_dump_json(indent=2).encode()
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/risk/build":
            body = load_risk_build_report().model_dump_json(indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/risk":
            from warehouse.research.risk.api import risk_api_schema

            body = json.dumps(risk_api_schema(), indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            body = build_status_report().model_dump_json(indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/api/risk":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            from warehouse.research.risk.api import evaluate_risk_json

            status, body_text = evaluate_risk_json(raw)
            body = body_text.encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return  # quiet default request logging


def serve(
    host: str = "127.0.0.1", port: int = 8765, *, risk: bool = False
) -> None:
    DashboardHandler.risk_landing = risk
    server = HTTPServer((host, port), DashboardHandler)
    if risk:
        print(f"Risk build: http://{host}:{port}/")
    else:
        print(f"Catalog:    http://{host}:{port}/")
        print(f"Data plane: http://{host}:{port}/data")
        print(f"Research:   http://{host}:{port}/research")
    print(f"Risk build: http://{host}:{port}/risk")
    print(f"Build API:  http://{host}:{port}/api/risk/build")
    print(f"Status API: http://{host}:{port}/api/status")
    print(f"Risk API:   http://{host}:{port}/api/risk")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
