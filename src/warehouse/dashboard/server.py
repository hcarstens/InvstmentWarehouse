"""Minimal HTTP dashboard — living status report."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

from warehouse.dashboard.status import build_status_report

if TYPE_CHECKING:
    from socketserver import ThreadingMixIn


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge badge-{kind}">{html.escape(text)}</span>'


def _readiness_kind(readiness: str) -> str:
    return {"live": "ok", "partial": "warn", "stub": "muted"}.get(readiness, "muted")


def _phase_kind(status: str) -> str:
    return {"complete": "ok", "in_progress": "warn", "planned": "muted"}.get(status, "muted")


def _panel_kind(status: str) -> str:
    return {"live": "ok", "stub": "warn", "planned": "muted"}.get(status, "muted")


def render_html() -> str:
    report = build_status_report()
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
    footer {{ color: #666; font-size: 0.85rem; margin-top: 1.5rem; }}
  </style>
</head>
<body>
  <h1>Investment Warehouse</h1>
  <p class="subtitle">Living status report · v{html.escape(report.version)} · {html.escape(report.app_env)}</p>
  <p><strong>North star:</strong> {html.escape(report.north_star)} · <strong>Build order:</strong> {html.escape(report.build_order)}</p>

  <div class="metrics">
    <div class="metric"><strong>{report.live_panel_count}</strong> live panels</div>
    <div class="metric"><strong>{report.planned_panel_count}</strong> planned panels</div>
    <div class="metric"><strong>{len(report.workflows)}</strong> workflows</div>
    <div class="metric"><strong>{len(report.planes)}</strong> planes</div>
  </div>

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

  <footer>Generated {report.generated_at.isoformat()} · auto-refresh 30s · <a href="/api/status">JSON</a></footer>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/dashboard"):
            body = render_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
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

    def log_message(self, format: str, *args: object) -> None:
        return  # quiet default request logging


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = HTTPServer((host, port), DashboardHandler)
    print(f"Dashboard: http://{host}:{port}/")
    print(f"Status API: http://{host}:{port}/api/status")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
