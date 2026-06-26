"""Risk API structured logging and failure surfacing."""

from __future__ import annotations

from typing import Any

import structlog

from warehouse.config import get_settings
from warehouse.infra.notify import dispatch_risk_alert
from warehouse.research.risk.models import (
    AssetPortfolio,
    RiskRequest,
    RiskResult,
)

logger = structlog.get_logger(__name__)


def log_risk_evaluated(
    result: RiskResult,
    *,
    request: RiskRequest,
    manifest: AssetPortfolio,
    surface: str,
) -> None:
    settings = get_settings()
    level_1 = result.report.level_1_portfolio
    fields: dict[str, Any] = {
        "surface": surface,
        "horizon_years": str(request.horizon.years),
        "fingerprint": result.report.input_fingerprint,
        "annualized_vol": str(level_1.annualized_volatility.value),
        "parametric_var": str(level_1.parametric_var.value),
        "model_version": result.report.model_version,
        "run_scenarios": request.run_scenarios.value,
        "manifest_source": manifest.source,
        "manifest_complexity": manifest.complexity,
    }
    if settings.risk_log_inputs:
        logger.info(
            "risk_evaluated",
            portfolio_id=manifest.portfolio_id,
            notional_usd=(
                str(request.notional_usd) if request.notional_usd else None
            ),
            **fields,
        )
    else:
        logger.info("risk_evaluated", **fields)


def record_risk_failure(
    err: BaseException,
    *,
    surface: str,
    http_status: int | None = None,
    **context: Any,
) -> None:
    """Log risk failure, optionally notify, never swallow the error."""
    settings = get_settings()
    fields: dict[str, Any] = {
        "surface": surface,
        "error_type": type(err).__name__,
        "error": str(err),
        **context,
    }
    if http_status is not None:
        fields["http_status"] = http_status

    logger.error("risk_evaluation_failed", **fields)

    if not settings.risk_notify_on_error:
        return

    subject = f"[warehouse] risk API failure ({surface})"
    body_lines = [
        f"surface: {surface}",
        f"error_type: {type(err).__name__}",
        f"error: {err}",
    ]
    if http_status is not None:
        body_lines.append(f"http_status: {http_status}")
    for key, value in context.items():
        body_lines.append(f"{key}: {value}")
    body = "\n".join(body_lines)

    try:
        dispatch_risk_alert(subject, body, settings=settings, extra=fields)
    except RuntimeError as notify_err:
        logger.error(
            "risk_notify_dispatch_failed",
            notify_error=str(notify_err),
            **fields,
        )
        raise notify_err from err
