"""Configuration loading tests."""

from warehouse.config import default_config_path, get_settings, repo_root


def test_default_config_path_exists() -> None:
    path = default_config_path()
    assert path.is_file()
    assert path.name == "development.toml"


def test_settings_from_config_file() -> None:
    import os

    os.environ.pop("DATABASE_URL", None)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.app_env == "development"
    assert settings.log_level == "debug"
    assert settings.database_url == "sqlite:///./data/warehouse_dev.db"
    assert settings.tax_config_version == "2026.01"
    assert settings.walk_forward_purge_days == 5
    assert settings.risk_model_version == "2026.02"
    assert settings.risk_var_alpha == 0.95
    assert settings.risk_es_alpha == 0.975
    assert settings.risk_vol_window_days == 252
    assert settings.risk_log_inputs is False
    assert settings.job_queue_url == ""


def test_repo_root_contains_configs() -> None:
    assert (repo_root() / "configs" / "development.toml").is_file()
