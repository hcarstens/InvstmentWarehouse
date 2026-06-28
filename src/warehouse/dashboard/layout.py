"""Shared dashboard HTML shell — CSS, nav, page wrapper."""

from __future__ import annotations

import html
from datetime import datetime

from warehouse.dashboard.navigation import PAGES

_STYLES = """
    :root {
      font-family: system-ui, sans-serif;
      color: #1a1a1a;
      background: #f6f7f9;
    }
    body { max-width: 1100px; margin: 0 auto; padding: 1.5rem; }
    h1 { margin-bottom: 0.25rem; }
    .subtitle { color: #555; margin-top: 0; }
    nav.site-nav {
      display: flex; flex-wrap: wrap; gap: 0.35rem 0.75rem;
      margin: 1rem 0; padding: 0.75rem 1rem; background: #fff;
      border: 1px solid #ddd; border-radius: 8px; font-size: 0.9rem;
    }
    nav.site-nav a { color: #1d4ed8; text-decoration: none; }
    nav.site-nav a.active { font-weight: 700; color: #1e3a8a; }
    nav.site-nav a:hover { text-decoration: underline; }
    .metrics { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }
    .metric {
      background: #fff; border: 1px solid #ddd; border-radius: 8px;
      padding: 1rem 1.25rem; min-width: 140px;
    }
    .metric strong { display: block; font-size: 1.5rem; }
    .plane-cards {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
      gap: 1rem; margin: 1rem 0;
    }
    .plane-card {
      background: #fff; border: 1px solid #ddd; border-radius: 8px;
      padding: 1rem 1.25rem;
    }
    .plane-card h3 { margin: 0 0 0.35rem; font-size: 1rem; }
    .plane-card p { margin: 0.35rem 0; font-size: 0.88rem; color: #444; }
    section {
      background: #fff; border: 1px solid #ddd; border-radius: 8px;
      padding: 1rem 1.25rem; margin: 1rem 0;
    }
    table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
    th, td {
      text-align: left; padding: 0.45rem 0.5rem;
      border-bottom: 1px solid #eee; vertical-align: top;
    }
    th { color: #444; }
    code { font-size: 0.85em; }
    .badge {
      display: inline-block; padding: 0.15rem 0.5rem;
      border-radius: 999px; font-size: 0.75rem;
      font-weight: 600; text-transform: uppercase;
    }
    .badge-ok { background: #d1fae5; color: #065f46; }
    .badge-warn { background: #fef3c7; color: #92400e; }
    .badge-muted { background: #e5e7eb; color: #374151; }
    .badge-err { background: #fee2e2; color: #991b1b; }
    .error-banner {
      background: #fee2e2; border: 1px solid #fca5a5; color: #991b1b;
      padding: 0.75rem 1rem; border-radius: 8px; margin: 1rem 0;
    }
    footer { color: #666; font-size: 0.85rem; margin-top: 1.5rem; }
    .search { margin-bottom: 0.75rem; }
"""


def badge(text: str, kind: str) -> str:
    return f'<span class="badge badge-{kind}">{html.escape(text)}</span>'


def readiness_badge(readiness: str) -> str:
    kind = {"live": "ok", "partial": "warn", "stub": "muted"}.get(
        readiness, "muted"
    )
    return badge(readiness, kind)


def phase_badge(status: str) -> str:
    kind = {"complete": "ok", "in_progress": "warn", "planned": "muted"}.get(
        status, "muted"
    )
    return badge(status, kind)


def panel_badge(status: str) -> str:
    kind = {"live": "ok", "stub": "warn", "planned": "muted"}.get(
        status, "muted"
    )
    return badge(status, kind)


def infra_badge(status: str) -> str:
    kind = {
        "ok": "ok",
        "skipped": "muted",
        "warn": "warn",
        "error": "err",
    }.get(status, "muted")
    return badge(status, kind)


def render_nav(*, active_page_id: str) -> str:
    links = []
    for page in PAGES:
        cls = ' class="active"' if page.page_id == active_page_id else ""
        links.append(
            f'<a href="{html.escape(page.path)}"{cls}>'
            f"{html.escape(page.nav_label)}</a>"
        )
    joined = "".join(links)
    return f'<nav class="site-nav" aria-label="Dashboard">{joined}</nav>'


def wrap_page(
    *,
    title: str,
    subtitle: str,
    body: str,
    active_page_id: str,
    generated_at: datetime,
    footer_extra: str = "",
) -> str:
    nav = render_nav(active_page_id=active_page_id)
    footer_bits = [
        f"Generated {generated_at.isoformat()}",
        "auto-refresh 30s",
        '<a href="/api/status">status API</a>',
        '<a href="/api/health">health</a>',
    ]
    if footer_extra:
        footer_bits.append(footer_extra)
    footer_html = " · ".join(footer_bits)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="30">
  <title>{html.escape(title)}</title>
  <style>{_STYLES}</style>
</head>
<body>
  <h1>Investment Warehouse</h1>
  <p class="subtitle">{html.escape(subtitle)}</p>
  {nav}
  {body}
  <footer>{footer_html}</footer>
</body>
</html>"""
