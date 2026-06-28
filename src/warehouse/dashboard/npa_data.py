"""Non-performing-asset panel data (pa2) — real synthetic system state.

Drives the NPA panel off an in-process ``founder_executive`` rung-4 household
(no DB needed, §9): it carries a concentrated AAPL loss lot (sustained
drawdown) *and* an alternatives sleeve with a stale mark + a due capital call,
so a single household exercises positions + alternatives + manifest flags.
Per the human gate these are alerts only — nothing is staged or sold. Failures
surface in the panel's ``error`` field rather than disappearing (CLAUDE.md).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from warehouse.config import get_settings
from warehouse.decision.analyst import NpaFlag, flag_non_performing
from warehouse.research.synthetic import emit_synthetic_household
from warehouse.research.synthetic.fixture_views import (
    lot_positions_from_fixture,
    smoke_as_of_date,
)

_NPA_COHORT = "founder_executive"
_NPA_SEED = 11
_NPA_RUNG = 4


class NpaPanelData(BaseModel):
    household_id: str
    cohort_id: str
    as_of_date: date
    config_version: str
    position_count: int
    alt_count: int
    flags: list[NpaFlag]
    panel_status: str = "live"
    error: str | None = None


def load_npa_dashboard() -> NpaPanelData:
    try:
        # founder_executive can fail IPS validation at some seeds; we only need
        # its lots + alt sleeve, so emit unvalidated (mirrors pa0/pa1, §9).
        bundle = emit_synthetic_household(
            cohort_id=_NPA_COHORT,
            seed=_NPA_SEED,
            rung=_NPA_RUNG,
            validate=False,
        )
        fixture = bundle.fixture
        as_of = smoke_as_of_date(fixture)
        positions = lot_positions_from_fixture(fixture)
        alts = fixture.alternative_holdings

        settings = get_settings()
        result = flag_non_performing(
            positions,
            alts,
            bundle.ips,
            household_id=fixture.household_id,
            as_of=as_of,
            config_version=settings.analyst_config_version,
            stale_mark_days=settings.analyst_stale_mark_days,
            drawdown_pct=Decimal(str(settings.analyst_npa_drawdown_pct)),
            sustained_years=Decimal(str(settings.analyst_npa_sustained_years)),
        )
        return NpaPanelData(
            household_id=fixture.household_id,
            cohort_id=_NPA_COHORT,
            as_of_date=as_of,
            config_version=result.config_version,
            position_count=len(positions),
            alt_count=len(alts),
            flags=result.flags,
        )
    except Exception as err:
        return NpaPanelData(
            household_id="(unavailable)",
            cohort_id=_NPA_COHORT,
            as_of_date=date.today(),
            config_version="(unavailable)",
            position_count=0,
            alt_count=0,
            flags=[],
            panel_status="error",
            error=str(err),
        )
