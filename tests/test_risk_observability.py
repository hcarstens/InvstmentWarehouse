"""Risk API observability and notification tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from warehouse.config import Settings, get_settings
from warehouse.infra.notify.dispatch import dispatch_risk_alert
from warehouse.research.risk.api import evaluate_risk_json, risk_api_schema
from warehouse.research.risk.observability import record_risk_failure


def test_risk_api_schema_documents_notifications() -> None:
    schema = risk_api_schema()
    assert "notifications" in schema
    assert "risk_notify_email_enabled" in schema["notifications"]
    assert "risk_notify_messaging_webhook_url" in schema["notifications"]


def test_record_risk_failure_logs_without_notify_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("RISK_NOTIFY_ON_ERROR", "false")
    get_settings.cache_clear()

    with patch(
        "warehouse.research.risk.observability.dispatch_risk_alert"
    ) as notify:
        record_risk_failure(
            ValueError("bad weights"),
            surface="test",
            http_status=422,
        )
        notify.assert_not_called()

    get_settings.cache_clear()
    monkeypatch.delenv("RISK_NOTIFY_ON_ERROR", raising=False)


def test_evaluate_risk_json_records_invalid_json_failure() -> None:
    with patch("warehouse.research.risk.api.record_risk_failure") as record:
        status, body = evaluate_risk_json("{not json")
        assert status == 400
        assert "Invalid JSON" in json.loads(body)["error"]
        record.assert_called_once()
        err = record.call_args.args[0]
        assert isinstance(err, json.JSONDecodeError)


def test_dispatch_messaging_posts_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        risk_notify_on_error=True,
        risk_notify_messaging_enabled=True,
        risk_notify_messaging_webhook_url="https://hooks.example/risk",
        risk_notify_messaging_channel="alerts",
    )
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_open = MagicMock()
    mock_open.__enter__.return_value = mock_resp
    mock_open.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=mock_open) as urlopen:
        dispatch_risk_alert(
            "subject",
            "body",
            settings=settings,
            extra={"surface": "test"},
        )
        urlopen.assert_called_once()
        req = urlopen.call_args.args[0]
        assert req.full_url == "https://hooks.example/risk"
        payload = json.loads(req.data.decode())
        assert payload["channel"] == "alerts"
        assert payload["subject"] == "subject"


def test_dispatch_email_skips_without_smtp_host() -> None:
    settings = Settings(
        risk_notify_on_error=True,
        risk_notify_email_enabled=True,
        risk_notify_email_to="ops@example.com",
        risk_notify_smtp_host="",
    )
    with patch("smtplib.SMTP") as smtp:
        dispatch_risk_alert("subject", "body", settings=settings)
        smtp.assert_not_called()
