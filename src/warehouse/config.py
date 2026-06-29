"""Application configuration loaded from configs/ (not secrets)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
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

    # Portfolio Optimization v1 (po0) — constrained mean-variance QP.
    # Version-pinned for audit replay (CLAUDE.md: pin decision inputs). λ is a
    # PLATFORM prior (§B.6), not calibrated per household from IPS risk
    # tolerance — one efficient-frontier point at a fixed risk aversion. It is
    # calibrated against the §9 HNW fixtures so the interior rung-3 book gives
    # a sensible multi-sleeve target while the concentrated rung-4 books bind
    # their sleeve caps; the acceptance tests are property-based (λ-monotone,
    # binding clip, zero-Δ), so they do not depend on this exact magnitude.
    # qp_tolerance / qp_max_iters bound the projected-gradient ascent.
    optimizer_config_version: str = "2026.06"
    risk_aversion_lambda: float = 6.0
    qp_tolerance: float = 1e-9
    qp_max_iters: int = 5000
    # po1 turnover budget (§B.3): the hard ‖Δw‖₁ ≤ τ cap reads
    # ``ips.turnover_budget_pct`` per household (no-op when unset → byte-
    # identical po0). The pin below is DEMO-ONLY: the §9 cohort IPS leaves
    # turnover_budget_pct unset, so the dashboard loader injects this labelled
    # budget (model_copy on the IPS) to show a live "within budget"/"capped"
    # state. It is not a household policy. po1 leaves optimizer_config_version
    # at 2026.06 — the solver/objective are unchanged; the budget adds an
    # optional convex projection (ROUTE B), a no-op without a budget.
    optimizer_demo_turnover_budget_pct: float = 0.15

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
    risk_dashboard_horizon_years: float = 5.0
    risk_dashboard_demo_overlay: bool = True

    risk_notify_on_error: bool = True
    risk_notify_email_enabled: bool = False
    risk_notify_email_to: str = ""
    risk_notify_email_from: str = "warehouse-noreply@localhost"
    risk_notify_smtp_host: str = ""
    risk_notify_smtp_port: int = 587
    risk_notify_messaging_enabled: bool = False
    risk_notify_messaging_webhook_url: str = ""
    risk_notify_messaging_channel: str = "risk-api"

    reconcile_max_stale_days: int = 7

    # Portfolio Manager — ℍ_Allocation axiom scoring thresholds.
    # Version-pinned for audit replay (CLAUDE.md: pin decision inputs).
    pm_axiom_config_version: str = "2026.06"
    pm_effective_bets_pass: float = 3.0
    pm_effective_bets_warn: float = 2.0
    pm_stress_breach: float = -0.35
    pm_stress_warn: float = -0.25
    pm_drift_warn: float = 0.03
    pm_binding_constraint_warn: int = 3

    # Portfolio Analyst — ℍ_PortfolioAnalyst checkpoint thresholds.
    # Version-pinned for audit replay. WARN/BREACH are magnitudes of the
    # (annualized where present) active return vs the ex-ante class assumption;
    # calibrated against the §9 HNW fixtures so rung-3 sleeves WARN and the
    # founder concentrated drawdown lot BREACHes, while a zero-active probe
    # PASSes. min_holding_years is the floor below which active_annualized is
    # not_computed (annualizing sub-six-month windows amplifies noise).
    analyst_config_version: str = "2026.06"
    analyst_residual_warn: float = 0.025
    analyst_residual_breach: float = 0.06
    analyst_min_holding_years: float = 0.5

    # Portfolio Analyst — synthetic-thesis kill-criteria calibration (pa1).
    # These are the default kill thresholds stamped on synthetic theses
    # (emit-side), pinned to analyst_config_version for audit replay. Kill
    # criteria are pre-committed ON the thesis (per position); these are the
    # cohort defaults. A concentrated single-issuer lot gets the tighter
    # drawdown floor so the §9 concentrated_stress fixture trips a real breach.
    analyst_kill_drawdown_pct: float = -0.30
    analyst_kill_concentrated_drawdown_pct: float = -0.10
    analyst_kill_residual_cap: float = 0.10
    analyst_kill_min_liquidity_tier: int = 4

    # Portfolio Analyst — non-performing-asset (NPA) flag thresholds (pa2).
    # Reason-coded, advisory-only flags: they surface on the dashboard and
    # feed the approval gate; they NEVER become optimizer constraints or stage
    # trades (CLAUDE.md human gate). Pinned to analyst_config_version for audit
    # replay. drawdown_pct/sustained_years gate the sustained-drawdown rule (a
    # lot below cost beyond the threshold *and* held past the window — a fresh
    # dip is not flagged); stale_mark_days ages an alt's last manual mark
    # (semi-annual marking expected for PE); the missed-call rule needs no
    # extra threshold (a scheduled call due on/before as_of with capital still
    # unfunded). Calibrated against §9: founder_executive rung 4 trips
    # sustained-drawdown + stale-mark + missed-call.
    analyst_stale_mark_days: int = 180
    analyst_npa_drawdown_pct: float = -0.10
    analyst_npa_sustained_years: float = 1.0

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
