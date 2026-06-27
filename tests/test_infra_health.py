"""Infrastructure health check tests."""

from warehouse.config import Settings, get_settings
from warehouse.infra.health import (
    check_database,
    check_job_queue,
    check_object_store,
    check_risk_notify_config,
    run_infra_checks,
)


def test_run_infra_checks_all_pass_in_dev() -> None:
    get_settings.cache_clear()
    checks = run_infra_checks()
    assert len(checks) == 6
    assert all(c.status in {"ok", "skipped", "warn"} for c in checks), [
        (c.component, c.status, c.error) for c in checks if c.status == "error"
    ]


def test_sqlite_database_check_ok() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    result = check_database(settings)
    assert result.status == "ok"
    assert "SQLite connected" in result.detail
    assert result.error is None


def test_job_queue_skipped_when_empty() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        job_queue_url="",
    )
    result = check_job_queue(settings)
    assert result.status == "skipped"
    assert "In-process" in result.detail


def test_object_store_skipped_in_early_dev() -> None:
    settings = get_settings()
    result = check_object_store(settings)
    assert result.status == "skipped"
    assert "Phase 5" in result.detail


def test_risk_notify_skipped_when_master_switch_off() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        risk_notify_on_error=False,
    )
    result = check_risk_notify_config(settings)
    assert result.status == "skipped"
    assert "disabled" in result.detail


def test_risk_notify_warns_when_email_enabled_without_smtp() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        risk_notify_on_error=True,
        risk_notify_email_enabled=True,
        risk_notify_email_to="ops@example.com",
        risk_notify_smtp_host="",
    )
    result = check_risk_notify_config(settings)
    assert result.status == "warn"
    assert "smtp_host empty" in result.detail
    assert result.error is not None


def test_risk_notify_ok_when_messaging_configured() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        risk_notify_on_error=True,
        risk_notify_messaging_enabled=True,
        risk_notify_messaging_webhook_url="https://hooks.example/risk",
    )
    result = check_risk_notify_config(settings)
    assert result.status == "ok"
    assert "messaging" in result.detail
