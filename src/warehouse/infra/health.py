"""Live infrastructure health checks — errors bubble to surface."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import make_url

from warehouse.config import Settings, get_settings
from warehouse.infra.db import create_db_engine
from warehouse.infra.notify.dispatch import notify_config_gaps


class InfraCheck(BaseModel):
    component: str
    status: str  # ok | skipped | warn | error
    detail: str
    error: str | None = None


def _check_writable_dir(path: Path, component: str) -> InfraCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok")
        probe.unlink()
    except OSError as err:
        return InfraCheck(
            component=component,
            status="error",
            detail=f"Path not writable: {path}",
            error=str(err),
        )
    return InfraCheck(
        component=component,
        status="ok",
        detail=f"Writable at {path.resolve()}",
    )


def check_database(settings: Settings) -> InfraCheck:
    url = make_url(settings.database_url)
    if url.drivername != "sqlite":
        return InfraCheck(
            component="Database",
            status="skipped",
            detail=f"External DB ({url.drivername}) — Phase 5 docker-compose",
        )

    if url.database and url.database != ":memory:":
        db_path = Path(url.database)
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            return InfraCheck(
                component="Database",
                status="error",
                detail=f"Cannot create SQLite directory: {db_path.parent}",
                error=str(err),
            )

    try:
        engine = create_db_engine(settings)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as err:
        return InfraCheck(
            component="Database",
            status="error",
            detail=f"SQLite connection failed: {settings.database_url}",
            error=str(err),
        )

    location = url.database if url.database else ":memory:"
    return InfraCheck(
        component="Database",
        status="ok",
        detail=f"SQLite connected ({location})",
    )


def check_local_data_path(settings: Settings) -> InfraCheck:
    return _check_writable_dir(Path(settings.local_data_path), "Local data")


def check_research_sandbox(settings: Settings) -> InfraCheck:
    return _check_writable_dir(
        Path(settings.research_sandbox_path), "Research sandbox"
    )


def check_job_queue(settings: Settings) -> InfraCheck:
    if not settings.job_queue_url.strip():
        return InfraCheck(
            component="Job queue",
            status="skipped",
            detail=(
                "In-process jobs (no Redis) — Redis queue deferred to Phase 5"
            ),
        )

    try:
        import redis
    except ImportError as err:
        return InfraCheck(
            component="Job queue",
            status="error",
            detail="Redis URL configured but redis package not installed",
            error=str(err),
        )

    try:
        client = redis.from_url(
            settings.job_queue_url, socket_connect_timeout=1
        )
        client.ping()
    except Exception as err:
        return InfraCheck(
            component="Job queue",
            status="error",
            detail=f"Redis unreachable: {settings.job_queue_url}",
            error=str(err),
        )

    return InfraCheck(
        component="Job queue",
        status="ok",
        detail=f"Redis reachable ({settings.job_queue_url})",
    )


def check_object_store(settings: Settings) -> InfraCheck:
    if not settings.object_store_endpoint.strip():
        return InfraCheck(
            component="Object store",
            status="skipped",
            detail=(
                f"Local filesystem ({settings.local_data_path}) — "
                "object store deferred to Phase 5"
            ),
        )

    return InfraCheck(
        component="Object store",
        status="skipped",
        detail=(
            "S3 endpoint configured; connectivity check deferred to Phase 5"
        ),
    )


def check_risk_notify_config(settings: Settings) -> InfraCheck:
    if not settings.risk_notify_on_error:
        return InfraCheck(
            component="Risk alerts",
            status="skipped",
            detail="risk_notify_on_error=false — failure alerts disabled",
        )

    gaps = notify_config_gaps(settings)
    if gaps:
        return InfraCheck(
            component="Risk alerts",
            status="warn",
            detail="; ".join(gaps),
            error="Alerts will not be delivered until configured",
        )

    channels = []
    if settings.risk_notify_email_enabled:
        channels.append("email")
    if settings.risk_notify_messaging_enabled:
        channels.append("messaging")
    if channels:
        return InfraCheck(
            component="Risk alerts",
            status="ok",
            detail=f"Failure alerts via {', '.join(channels)}",
        )

    return InfraCheck(
        component="Risk alerts",
        status="skipped",
        detail=(
            "risk_notify_on_error=true but no email/messaging channels enabled"
        ),
    )


def run_infra_checks(settings: Settings | None = None) -> list[InfraCheck]:
    cfg = settings or get_settings()
    return [
        check_database(cfg),
        check_local_data_path(cfg),
        check_research_sandbox(cfg),
        check_job_queue(cfg),
        check_object_store(cfg),
        check_risk_notify_config(cfg),
    ]


def infra_summary(checks: list[InfraCheck]) -> str:
    errors = [c for c in checks if c.status == "error"]
    if errors:
        names = ", ".join(c.component for c in errors)
        raise RuntimeError(f"Infrastructure health check failed: {names}")
    ok = sum(1 for c in checks if c.status == "ok")
    skipped = sum(1 for c in checks if c.status == "skipped")
    return f"{ok} ok, {skipped} skipped"
