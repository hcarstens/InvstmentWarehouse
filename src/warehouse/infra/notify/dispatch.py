"""Risk API notifications — email and messaging on failures."""

from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

import structlog

from warehouse.config import Settings, get_settings

logger = structlog.get_logger(__name__)


def _email_recipients(settings: Settings) -> list[str]:
    raw = settings.risk_notify_email_to.strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def dispatch_risk_alert(
    subject: str,
    body: str,
    *,
    settings: Settings | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Send configured email / messaging alerts. Logs and re-raises on send failure."""
    cfg = settings or get_settings()
    if not cfg.risk_notify_on_error:
        logger.debug(
            "risk_notify_skipped", reason="risk_notify_on_error=false"
        )
        return

    context = extra or {}
    if cfg.risk_notify_email_enabled:
        _send_email(subject, body, settings=cfg, extra=context)
    if cfg.risk_notify_messaging_enabled:
        _send_messaging(subject, body, settings=cfg, extra=context)


def _send_email(
    subject: str,
    body: str,
    *,
    settings: Settings,
    extra: dict[str, Any],
) -> None:
    recipients = _email_recipients(settings)
    if not recipients:
        logger.warning(
            "risk_email_skipped",
            reason="risk_notify_email_to empty",
            **extra,
        )
        return
    if not settings.risk_notify_smtp_host:
        logger.warning(
            "risk_email_skipped",
            reason="risk_notify_smtp_host empty",
            to=recipients,
            **extra,
        )
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.risk_notify_email_from
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    try:
        with smtplib.SMTP(
            settings.risk_notify_smtp_host,
            settings.risk_notify_smtp_port,
            timeout=10,
        ) as smtp:
            smtp.send_message(message)
    except OSError as err:
        logger.error(
            "risk_email_failed",
            error=str(err),
            smtp_host=settings.risk_notify_smtp_host,
            **extra,
        )
        raise RuntimeError(f"risk alert email failed: {err}") from err

    logger.info(
        "risk_email_sent",
        to=recipients,
        subject=subject,
        **extra,
    )


def _send_messaging(
    subject: str,
    body: str,
    *,
    settings: Settings,
    extra: dict[str, Any],
) -> None:
    webhook = settings.risk_notify_messaging_webhook_url.strip()
    if not webhook:
        logger.warning(
            "risk_messaging_skipped",
            reason="risk_notify_messaging_webhook_url empty",
            **extra,
        )
        return

    payload = {
        "channel": settings.risk_notify_messaging_channel,
        "subject": subject,
        "text": body,
        "source": "warehouse.risk_api",
        "extra": extra,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            status = resp.status
    except urlerror.URLError as err:
        logger.error(
            "risk_messaging_failed",
            error=str(err),
            webhook=webhook,
            **extra,
        )
        raise RuntimeError(f"risk alert messaging failed: {err}") from err

    logger.info(
        "risk_messaging_sent",
        webhook=webhook,
        http_status=status,
        channel=settings.risk_notify_messaging_channel,
        **extra,
    )
