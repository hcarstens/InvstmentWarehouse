"""pmw1 — falsifiers for the PM workout harness + renderer.

The workout drives the live ``pm.advise`` composite over synthetic cohorts
(no DB) and renders the AdviceBundle. These assert the stack is exercised, the
render is deterministic, and the artifact carries every section.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from warehouse.decision.pm_workout import (
    DEFAULT_PMW_COMBOS,
    PmWorkoutCase,
    render_pm_workout,
    run_pm_workout,
    write_pm_workout,
)

AS_OF = date(2026, 6, 30)
SEED = 42


def test_pm_workout_runs_all_cohorts() -> None:
    cases = run_pm_workout(seed=SEED, as_of=AS_OF)
    assert len(cases) == len(DEFAULT_PMW_COMBOS)
    cohorts = {c.cohort_id for c in cases}
    assert cohorts == {c for c, _ in DEFAULT_PMW_COMBOS}
    for case in cases:
        assert isinstance(case, PmWorkoutCase)
        o = case.advice
        # every leg of the composite came back populated
        assert o.risk.report is not None
        assert o.proposal.rebalance is not None
        assert o.narrative is not None
        assert o.tax is not None
        assert o.drift is not None
        # correlation_id threads the cohort + seed (trace contract §4.1)
        assert case.cohort_id in case.correlation_id
        assert f"s{SEED}" in case.correlation_id


def test_pm_workout_deterministic() -> None:
    first = render_pm_workout(
        run_pm_workout(seed=SEED, as_of=AS_OF), as_of=AS_OF, seed=SEED
    )
    second = render_pm_workout(
        run_pm_workout(seed=SEED, as_of=AS_OF), as_of=AS_OF, seed=SEED
    )
    assert first == second


def test_pm_workout_single_cohort() -> None:
    cases = run_pm_workout(
        combos=(("concentrated_stress", 4),), seed=SEED, as_of=AS_OF
    )
    assert len(cases) == 1
    assert cases[0].cohort_id == "concentrated_stress"
    assert cases[0].rung == 4


def test_render_contains_sections() -> None:
    cases = run_pm_workout(seed=SEED, as_of=AS_OF)
    md = render_pm_workout(cases, as_of=AS_OF, seed=SEED)
    assert "# Portfolio Manager Workout" in md
    assert "## Run ledger" in md
    assert "`op=pm.advise`" in md
    assert "Persona of The Portfolio Manager" in md
    assert "pm_workout_implementation.md" in md
    for marker in (
        "### 1 · Synthetic portfolio vs IPS policy",
        "### 2 · Risk report",
        "### 3 · Recommendation (optimizer)",
        "### 4 · Policy monitoring",
        "### 5 · Tax overlay",
        "### 7 · Portfolio Manager diagnostic",
    ):
        assert marker in md, marker


def test_write_pm_workout_round_trips(tmp_path: Path) -> None:
    out = tmp_path / "workout.md"
    path, cases = write_pm_workout(
        combos=(("general_hnw", 3),),
        seed=SEED,
        as_of=AS_OF,
        out_path=out,
    )
    assert path == out
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Portfolio Manager Workout")
    assert len(cases) == 1
