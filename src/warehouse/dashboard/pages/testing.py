"""Testing matrix dashboard page — cross-cutting QA evidence."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from warehouse.dashboard.layout import wrap_page
from warehouse.dashboard.render_testing import render_testing_matrix
from warehouse.dashboard.status import build_status_report
from warehouse.dashboard.testing_data import TestingReport, load_testing_report


class TestingPageData(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    report: TestingReport


def load_testing_page() -> TestingPageData:
    return TestingPageData(report=load_testing_report())


def render_testing_page(data: TestingPageData | None = None) -> str:
    bundle = data or load_testing_page()
    status = build_status_report()
    body = render_testing_matrix(bundle.report)
    subtitle = (
        f"Software testing · {status.version} · {status.app_env} · "
        f"<code>warehouse test report</code>"
    )
    return wrap_page(
        title="Investment Warehouse — Testing",
        subtitle=subtitle,
        body=body,
        active_page_id="testing",
        generated_at=bundle.generated_at,
        footer_extra='<a href="/api/testing">testing API</a>',
    )
