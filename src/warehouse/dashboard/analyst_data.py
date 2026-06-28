"""Kill-criteria watch dashboard data (pa1) — real synthetic system state.

Drives the watch panel off an in-process ``concentrated_stress`` household plus
its co-emitted theses (no DB needed, §9): emit → attribute → monitor kill
criteria. The panel shows live ``KillBreach`` alerts; per the human gate these
are alerts only — nothing is ever staged or sold. Failures surface in the
panel's ``error`` field rather than disappearing (CLAUDE.md).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from warehouse.config import get_settings
from warehouse.decision.analyst import (
    KillBreach,
    ThesisStore,
    evaluate_attribution,
    evaluate_kill_criteria,
    instrument_key,
    score_analyst_checkpoints,
)
from warehouse.research.risk.scenarios import assumptions_for
from warehouse.research.synthetic import (
    emit_synthetic_household,
    emit_synthetic_theses,
    synthetic_thesis_as_of,
)
from warehouse.research.synthetic.fixture_views import (
    lot_positions_from_fixture,
)

_WATCH_COHORT = "concentrated_stress"
_WATCH_SEED = 42
_WATCH_RUNG = 4


class KillCriteriaWatchData(BaseModel):
    household_id: str
    cohort_id: str
    as_of_date: date
    thesis_count: int
    documented_positions: int
    breaches: list[KillBreach]
    checkpoint_1: str
    panel_status: str = "live"
    error: str | None = None


def load_kill_criteria_dashboard() -> KillCriteriaWatchData:
    try:
        # concentrated_stress fails IPS validation at seed 42 (AAPL
        # concentration) — emit unvalidated; we only need its lots (§9).
        bundle = emit_synthetic_household(
            cohort_id=_WATCH_COHORT,
            seed=_WATCH_SEED,
            rung=_WATCH_RUNG,
            validate=False,
        )
        fixture = bundle.fixture
        as_of = synthetic_thesis_as_of(fixture)
        positions = lot_positions_from_fixture(fixture)
        theses = emit_synthetic_theses(fixture)
        store = ThesisStore.from_theses(theses)

        settings = get_settings()
        report = evaluate_attribution(
            positions,
            assumptions_for("base").class_expected_return,
            household_id=fixture.household_id,
            as_of=as_of,
            config_version=settings.analyst_config_version,
            min_holding_years=Decimal(str(settings.analyst_min_holding_years)),
        )
        active_by_key = {
            (pa.account_id, pa.ticker): pa.active_return
            for pa in report.positions
        }

        breaches: list[KillBreach] = []
        documented: set[tuple[str, str]] = set()
        for pos in positions:
            key = instrument_key(pos)
            thesis = store.get(pos.account_id, key)
            if thesis is None:
                continue
            documented.add((pos.account_id, key))
            breaches.extend(
                evaluate_kill_criteria(
                    pos,
                    thesis,
                    as_of=as_of,
                    active_return=active_by_key.get(
                        (pos.account_id, pos.ticker)
                    ),
                )
            )

        review = score_analyst_checkpoints(report, theses=store)
        return KillCriteriaWatchData(
            household_id=fixture.household_id,
            cohort_id=_WATCH_COHORT,
            as_of_date=as_of,
            thesis_count=len(store),
            documented_positions=len(documented),
            breaches=breaches,
            checkpoint_1=review.checkpoints["checkpoint_1"].value,
        )
    except Exception as err:
        return KillCriteriaWatchData(
            household_id="(unavailable)",
            cohort_id=_WATCH_COHORT,
            as_of_date=date.today(),
            thesis_count=0,
            documented_positions=0,
            breaches=[],
            checkpoint_1="not_documented",
            panel_status="error",
            error=str(err),
        )
