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
