"""Application configuration loaded from configs/ (not secrets)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic_settings.sources import TomlConfigSettingsSource


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    return repo_root() / "configs" / "development.toml"


def resolve_config_path() -> Path:
    override = os.getenv("WAREHOUSE_CONFIG")
    if override:
        path = Path(override)
        return path if path.is_absolute() else repo_root() / path
    return default_config_path()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/warehouse_dev.db"
    local_data_path: str = "./data"

    object_store_bucket: str = "warehouse-dev"
    object_store_endpoint: str = ""
    object_store_access_key: str = ""
    object_store_secret_key: str = ""

    job_queue_url: str = ""

    tax_config_version: str = "2026.01"
    fed_stcg_rate: float = 0.37
    fed_ltcg_rate: float = 0.20
    niit_rate: float = 0.038
    amt_rate: float = 0.28

    mip_optimizer_enabled: bool = True
    mip_max_trades: int = 3

    research_sandbox_path: str = "./runs/research"
    walk_forward_purge_days: int = 5

    risk_model_version: str = "2026.02"
    risk_diversification_factor: float = 0.85
    risk_fermi_confidence_width: float = 0.15
    risk_log_inputs: bool = False
    risk_var_alpha: float = 0.95
    risk_es_alpha: float = 0.975
    risk_vol_window_days: int = 252
    risk_stress_pack_version: str = "2026.01"

    household_rls_enabled: bool = False

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        config_path = resolve_config_path()
        local_path = repo_root() / "configs" / "local.toml"
        sources: list[PydanticBaseSettingsSource] = [
            init_settings,
            env_settings,
        ]
        if local_path.is_file():
            sources.append(TomlConfigSettingsSource(settings_cls, local_path))
        sources.append(TomlConfigSettingsSource(settings_cls, config_path))
        return tuple(sources)


@lru_cache
def get_settings() -> Settings:
    return Settings()
