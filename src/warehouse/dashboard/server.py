"""Minimal HTTP dashboard — living status report."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlparse

from warehouse.config import repo_root
from warehouse.dashboard.catalog import render_catalog
from warehouse.dashboard.navigation import PAGES
from warehouse.dashboard.pages.data import load_data_page, render_data_page
from warehouse.dashboard.pages.decision import (
    load_decision_page,
    render_decision_page,
)
from warehouse.dashboard.pages.execution import (
    load_execution_page,
    render_execution_page,
)
from warehouse.dashboard.pages.infra import load_infra_page, render_infra_page
from warehouse.dashboard.pages.reporting import (
    load_reporting_page,
    render_reporting_page,
)
from warehouse.dashboard.pages.research import (
    load_research_page,
    render_research_page,
)
from warehouse.dashboard.phase1_data import load_phase1_dashboard
from warehouse.dashboard.phase2_data import load_phase2_dashboard
from warehouse.dashboard.phase3_data import load_phase3_dashboard
from warehouse.dashboard.phase4_data import load_phase4_dashboard
from warehouse.dashboard.render_risk_build import render_risk_build_page
from warehouse.dashboard.risk_build_data import load_risk_build_report
from warehouse.dashboard.risk_data import load_risk_dashboard
from warehouse.dashboard.status import build_status_report

# Legacy /api/phaseN → plane page JSON (dd6). Bodies unchanged; headers mark deprecation.
_PHASE_API_SUCCESSORS: dict[str, tuple[str, ...]] = {
    "phase1": ("/api/pages/data",),
    "phase2": (
        "/api/pages/data",
        "/api/pages/execution",
        "/api/pages/infra",
    ),
    "phase3": ("/api/pages/decision", "/api/pages/research"),
    "phase4": (
        "/api/pages/data",
        "/api/pages/execution",
        "/api/pages/reporting",
    ),
}


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


class DashboardHandler(BaseHTTPRequestHandler):
    risk_landing: bool = False

    def _write_json(
        self,
        body: bytes,
        status: int,
        *,
        deprecation_successors: tuple[str, ...] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if deprecation_successors:
            self.send_header("Deprecation", "true")
            link = ", ".join(
                f'<{path}>; rel="successor-version"'
                for path in deprecation_successors
            )
            self.send_header("Link", link)
            notice = "use " + ", ".join(deprecation_successors)
            self.send_header("X-Deprecation-Notice", notice)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        if path_only == "/decision":
            body = render_decision_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path_only == "/execution":
            body = render_execution_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path_only == "/reporting":
            body = render_reporting_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path_only == "/infra":
            body = render_infra_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path_only == "/api/pages/infra":
            infra_data = load_infra_page()
            body = infra_data.model_dump_json(indent=2).encode()
            self._write_json(body, 200 if not infra_data.error else 503)
            return
        if path_only == "/api/pages/reporting":
            reporting_data = load_reporting_page()
            body = reporting_data.model_dump_json(indent=2).encode()
            self._write_json(body, 200 if not reporting_data.error else 503)
            return
        if path_only == "/api/pages/execution":
            execution_data = load_execution_page()
            body = execution_data.model_dump_json(indent=2).encode()
            self._write_json(body, 200 if not execution_data.error else 503)
            return
        if path_only == "/api/pages/decision":
            decision_data = load_decision_page()
            body = decision_data.model_dump_json(indent=2).encode()
            self._write_json(body, 200 if not decision_data.error else 503)
            return
        if path_only == "/api/pages/research":
            research_data = load_research_page()
            body = research_data.model_dump_json(indent=2).encode()
            self._write_json(body, 200 if not research_data.error else 503)
            return
        if path_only == "/api/pages/data":
            page_data = load_data_page(
                security_query=_security_query_from_path(self.path),
                custodian_id=_custodian_from_path(self.path),
            )
            body = page_data.model_dump_json(indent=2).encode()
            self._write_json(body, 200 if not page_data.error else 503)
            return
        if self.path.startswith("/api/phase4"):
            custodian = _custodian_from_path(self.path)
            phase4 = load_phase4_dashboard(custodian_id=custodian)
            body = phase4.model_dump_json(indent=2).encode()
            self._write_json(
                body,
                200 if not phase4.error else 503,
                deprecation_successors=_PHASE_API_SUCCESSORS["phase4"],
            )
            return
        if self.path.startswith("/api/phase3"):
            phase3 = load_phase3_dashboard()
            body = phase3.model_dump_json(indent=2).encode()
            self._write_json(
                body,
                200 if not phase3.error else 503,
                deprecation_successors=_PHASE_API_SUCCESSORS["phase3"],
            )
            return
        if self.path.startswith("/api/phase2"):
            phase2 = load_phase2_dashboard()
            body = phase2.model_dump_json(indent=2).encode()
            self._write_json(
                body,
                200 if not phase2.error else 503,
                deprecation_successors=_PHASE_API_SUCCESSORS["phase2"],
            )
            return
        if self.path.startswith("/api/phase1"):
            phase1 = load_phase1_dashboard(
                security_query=_security_query_from_path(self.path)
            )
            body = phase1.model_dump_json(indent=2).encode()
            self._write_json(
                body,
                200 if not phase1.error else 503,
                deprecation_successors=_PHASE_API_SUCCESSORS["phase1"],
            )
            return
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
    base = f"http://{host}:{port}"
    if risk:
        print(f"Risk build: {base}/")
    else:
        print(f"Catalog:    {base}/")
        for page in PAGES:
            if page.page_id in ("catalog", "risk_build"):
                continue
            print(f"{page.nav_label + ':':<11} {base}{page.path}")
    print(f"Risk build: {base}/risk")
    print(f"Build API:  {base}/api/risk/build")
    print(f"Status API: {base}/api/status")
    print(f"Risk API:   {base}/api/risk")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
