"""Infrastructure health check tests."""

from warehouse.config import Settings, get_settings
from warehouse.infra.health import (
    check_database,
    check_job_queue,
    check_object_store,
    run_infra_checks,
)


def test_run_infra_checks_all_pass_in_dev() -> None:
    get_settings.cache_clear()
    checks = run_infra_checks()
    assert len(checks) == 5
    assert all(c.status in {"ok", "skipped"} for c in checks), [
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
    assert "Phase 4" in result.detail
