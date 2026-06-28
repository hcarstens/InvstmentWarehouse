"""Portfolio Analyst — attribution + checkpoint diagnostic snapshots.

Audit/replay-critical, immutable. The headline per-position figure is
``active_return`` = total return − the ex-ante class assumption scaled to the
holding window (a policy/benchmark gap). Per Addendum A.3 it is **never**
called "alpha", "idiosyncratic", or "residual" — the beta-stripped
idiosyncratic quantity (axiom 1) is honestly ``not_computed``.

The decomposition ``total = expected_cumulative + active_return`` keeps both
components present at all times (¬M7 / checkpoint 7) — never a collapsed score.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from warehouse.data.security_master import AssetClass as SecurityAssetClass
from warehouse.research.risk.models import AssetClass as RiskAssetClass

# The honest label for the headline per-position figure (Addendum A.3): a
# policy/benchmark gap, not skill. Must contain none of alpha/idiosyncratic/
# residual (enforced by tests/test_analyst_attribution.py).
ACTIVE_RETURN_LABEL = "active return vs ex-ante class assumption"


class AnalystCheckpointScore(StrEnum):
    """7-checkpoint vocabulary — separate from the PM ``AxiomScore`` (§2).

    Mirrors the PM enum (``PASS | WARN | BREACH | NOT_COMPUTED``) plus
    ``NOT_DOCUMENTED`` for checkpoint 1 (thesis absent — first-class, not a
    faked pass). Kept distinct so the PM contract's frozen-adjacent enum is not
    widened.
    """

    PASS = "pass"
    WARN = "warn"
    BREACH = "breach"
    NOT_COMPUTED = "not_computed"
    NOT_DOCUMENTED = "not_documented"


class PositionAttribution(BaseModel):
    """Per-lot decomposition: ``total = expected_cumulative + active_return``.

    Both components are always present (¬M7 / checkpoint 7). ``active_return``
    is cumulative over the holding window; ``active_annualized`` is populated
    only when the window clears ``analyst_min_holding_years`` (A.5) — otherwise
    ``None`` (``not_computed``), never a noisy annualized number.
    """

    model_config = ConfigDict(frozen=True)

    lot_id: str
    account_id: str
    ticker: str | None
    security_asset_class: SecurityAssetClass
    risk_class: RiskAssetClass
    liquidity_tier: int  # carried so the report scores liquidity kills (pa1)
    holding_years: Decimal
    market_value: Decimal
    total_return: Decimal
    class_expected: Decimal  # annual class assumption — the mechanism
    expected_cumulative: Decimal  # class assumption scaled to the window
    active_return: Decimal  # total_return − expected_cumulative (cumulative)
    active_annualized: Decimal | None  # only when window ≥ min_holding_years


class AttributionReport(BaseModel):
    """Attribution snapshot — positions ordered by ``|active_return|``.

    ``portfolio_active_return`` is market-value-weighted (A.5); a raw sum over
    heterogeneous windows/bases would be meaningless. ``limitations`` surfaces
    the honest gaps in the report itself (dashboard-first).
    """

    model_config = ConfigDict(frozen=True)

    household_id: str
    as_of_date: date
    config_version: str
    positions: list[PositionAttribution]
    portfolio_active_return: Decimal
    limitations: list[str]


class KillCriterion(StrEnum):
    """The four pre-committed kill tests (pa1, §5).

    Each is *advisory only* — a breach raises an alert to the advisor, never an
    autonomous sell (CLAUDE.md human gate).
    """

    DRAWDOWN_VS_COST = "drawdown_vs_cost"
    RESIDUAL_CAP = "residual_cap"
    LIQUIDITY_FLOOR = "liquidity_floor"
    HORIZON = "horizon"


class KillCriteria(BaseModel):
    """Pre-specified falsification thresholds for a thesis (axiom 2).

    Every threshold is optional: only the criteria the advisor pre-committed
    are evaluated — an unset limit is never fabricated. ``max_active_residual``
    is only checked when an ``active_return`` is supplied (it needs the
    attribution leg); a bare position cannot compute it.
    """

    model_config = ConfigDict(frozen=True)

    # Breach if total_return ≤ this (a negative drawdown floor, e.g. −0.20).
    max_drawdown_vs_cost: Decimal | None = None
    # Breach if |active_return| ≥ this (a non-negative residual cap).
    max_active_residual: Decimal | None = None
    # Breach if liquidity_tier > this (1 = most liquid .. 5 = least).
    min_liquidity_tier: int | None = None
    # Breach if holding_years > this (the thesis horizon).
    max_holding_years: Decimal | None = None


class PositionThesis(BaseModel):
    """Falsifiable, effective-dated thesis for an instrument-in-account (pa1).

    ``effective_date`` is the pre-commitment date: the kill criteria must be
    set on or before the position's ``acquisition_date`` (axiom 2 — no
    hindsight); ``evaluate_kill_criteria`` raises if a thesis post-dates the
    lot. Audit/replay-critical → frozen + version-pinned.
    """

    model_config = ConfigDict(frozen=True)

    account_id: str
    instrument: str  # ticker (or security_id) — keyed account×instrument
    mechanism: str  # why we hold it (the thesis, one causal hop)
    effective_date: date  # pre-committed on/before acquisition_date
    kill_criteria: KillCriteria
    config_version: str


class KillBreach(BaseModel):
    """One tripped kill criterion — an ALERT, never a staged trade (pa1).

    ``observed`` is the live figure, ``threshold`` the pre-committed limit.
    Surfaced on the kill-criteria watch panel and flips checkpoint 1 to BREACH;
    the advisor decides — the system never sells (CLAUDE.md).
    """

    model_config = ConfigDict(frozen=True)

    account_id: str
    instrument: str
    criterion: KillCriterion
    observed: Decimal
    threshold: Decimal
    detail: str


class AnalystCheckpoint(BaseModel):
    """One scored checkpoint plus its honest detail line (dashboard row)."""

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    score: AnalystCheckpointScore
    detail: str


class AnalystReview(BaseModel):
    """7-checkpoint ℍ_PortfolioAnalyst diagnostic — audit snapshot.

    ``checkpoints`` is keyed ``checkpoint_1``..``checkpoint_7``; ``details``
    holds the matching honest-gap copy. Version-pinned via ``config_version``
    for audit replay.
    """

    model_config = ConfigDict(frozen=True)

    config_version: str
    checkpoints: dict[str, AnalystCheckpointScore]
    details: dict[str, str]
    headline: str
