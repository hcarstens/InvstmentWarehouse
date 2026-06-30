# PM Workout — Implementation Plan

**Status:** pmw1 **shipped** — in-process harness + `warehouse pm-workout` CLI
+ Markdown artifact; pure/advisory, no DB.
**Date:** 2026-06-30
**Owner:** decision plane (`warehouse.decision.pm_workout`)
**Inputs:**
[`heuristics/Persona of The Portfolio Manager.md`](heuristics/Persona%20of%20The%20Portfolio%20Manager.md)
(ℍ_Allocation — the 7-axiom lens the workout renders),
[`portfolio_manager_implementation.md`](portfolio_manager_implementation.md)
(pm0–pm2 — `pm.advise`, `build_working_set_from_bundle`, `score_pm_axioms`),
[`messaging_protocol.md`](messaging_protocol.md)
(§4.1 coordinator, §5 request catalog — the message vocabulary),
[`research/hnw_portfolios.md`](research/hnw_portfolios.md)
(cohorts + rung ladder),
[`synthetic_ips_implementation.md`](synthetic_ips_implementation.md)
(si1/si2 — `emit_synthetic_household`),
[`dev_contract_registry.md`](dev_contract_registry.md).

---

## 1. Principle — exercise the whole book, render the verdict

The PM workout is the **runnable replication of the production PM loop**: it
generates a synthetic household (portfolio + IPS), packages it as a process
message, dispatches it *from the Portfolio Manager tier*, and renders the
returned `AdviceBundle` as a human-readable workout. It is the
single-command answer to "is the decision stack functionally usable?".

It adds **no new `op`** and **no new engine** — it is a *driver + renderer*
over the already-shipped `pm.advise` composite (pm0–pm2). Like `pm.advise`
itself it is **pure + advisory**: it mutates nothing, needs no `Session`
(`DispatchContext(session=None)`; every leg is EVALUATE), and a leg that
raises is re-raised with its op/correlation_id note (CLAUDE.md errors-bubble),
so a broken stack fails loud rather than rendering a partial report.

```text
emit_synthetic_household(cohort, seed, rung)     ── generate portfolio + IPS
        │  → SyntheticHouseholdBundle
build_working_set_from_bundle(bundle)            ── the process message body
        │  → PmAdvisePayload {positions, ips, manifest, request}
Message(op="pm.advise", kind=EVALUATE)           ── the envelope
        │
dispatch_typed(ctx, msg, AdviceBundle)           ── dispatch FROM the PM
        │  → risk.evaluate · policy.check · optimizer.propose
        │    · attribution.evaluate · tax.scenario → score_pm_axioms
render_pm_workout(cases)                          ── report + recommendation
        └─► portfolio_manager_workout.md
```

---

## 2. Message vocabulary exercised

The workout fires exactly one top-level op; the PM composite nest-dispatches
the rest under the same `correlation_id`. Authority is
[`messaging_protocol.md`](messaging_protocol.md) §5 — this is the focused
subset the workout drives (all EVALUATE — pure, no mutation, no `Session`):

| `op` | kind | plane | role in the workout |
| --- | --- | --- | --- |
| `pm.advise` | EVALUATE *(composite)* | decision | top-level dispatch; returns the `AdviceBundle` (report + recommendation) |
| `risk.evaluate` | EVALUATE | research | whole-book risk report (vol, VaR/ES, variance contributions, stress replay) → §2 of the artifact |
| `policy.check` | EVALUATE | decision | IPS drift + concentration alerts → §1/§4 |
| `optimizer.propose` | EVALUATE | decision | TLH trades + MV rebalance w\* → §3 (the recommendation) |
| `attribution.evaluate` | EVALUATE | decision | per-position active-return attribution → §6 |
| `tax.scenario` | EVALUATE | decision | NIIT/AMT overlay (intentional $0 stub) → §5 |

No `QUERY` (positions come from the synthetic fixture, not the ledger) and no
`COMMAND` (nothing is persisted, gated, or staged). The acting ops
(`optimizer.persist` → `approval.*` → `orders.stage`, `report.build`) are out
of scope — the workout is advisory-only.

---

## 3. Scope — what ships vs deferred

### In scope (pmw1)

| Item | Where |
| --- | --- |
| `run_pm_workout_case` / `run_pm_workout` — generate + dispatch per cohort | `decision/pm_workout.py` |
| `PmWorkoutCase` (frozen) — inputs (`bundle`) + output (`advice`) | `decision/pm_workout.py` |
| `render_pm_workout(cases)` → Markdown (ledger + per-household §1–7) | `decision/pm_workout.py` |
| `write_pm_workout(...)` → write artifact, return `(path, cases)` | `decision/pm_workout.py` |
| `warehouse pm-workout` CLI (`--seed`/`--as-of`/`--cohort`/`--rung`/`--out`) | `cli.py` |
| Default combos — `general_hnw`, `uhnw_inherited`, `founder_executive` (rung 3), `concentrated_stress` (rung 4) | `DEFAULT_PMW_COMBOS` |
| Falsifiers | `tests/test_pm_workout.py` |

### Deferred (not pmw1)

| Item | Why |
| --- | --- |
| Dashboard panel reading the artifact | The e2e smoke panel already covers live `pm.advise` health (`/research`); a workout panel is additive — pmw2 if wanted. |
| DB-backed path (`build_working_set` + `report.build`) | The workout is the *synthetic* in-process loop by design; the DB path is the report-writer track (rw\*). |
| Free-text PM instruction in the envelope | `Message` has no NL field in v0; would extend the payload contract. |
| Non-zero tax deltas | Blocked on the tax estimate engine (po1-tax); honesty #5 stays `not_computed`. |

---

## 4. Run commands

```bash
# All four HNW cohorts → runs/pm_workout/portfolio_manager_workout.md
warehouse pm-workout

# Pin the as-of date and write to the repo-root artifact
warehouse pm-workout --as-of 2026-06-30 --out portfolio_manager_workout.md

# A single cohort at an explicit rung
warehouse pm-workout --cohort concentrated_stress --rung 4

# A different deterministic seed (same seed → byte-identical artifact)
warehouse pm-workout --seed 7
```

In-process — no `warehouse db bootstrap`, no `serve`, no external services.
The default output lives under `runs/` (gitignored, local state); pass `--out`
to write a tracked artifact.

Programmatic:

```python
from warehouse.decision.pm_workout import run_pm_workout, render_pm_workout
from datetime import date

cases = run_pm_workout(seed=42, as_of=date(2026, 6, 30))
md = render_pm_workout(cases, as_of=date(2026, 6, 30), seed=42)
```

---

## 5. Output schema (the artifact)

`portfolio_manager_workout.md` =
header (as-of, seed, persona/track links) →
**Run ledger** (one row per cohort: NAV, vol, worst stress, trades, tax Δ,
alert counts, PM headline) →
per-household sections **1–7**:

1. Synthetic portfolio vs IPS policy (manifest weights, target bands, lot
   drift — with the two-denominator note: manifest incl. alternatives vs
   lot-positions-only drift)
2. Risk report (vol, expected return, VaR/ES, variance contributions +
   effective bets, stress replay)
3. Recommendation — optimizer TLH trades + MV rebalance w\* (base vs stress)
4. Policy monitoring — IPS drift + concentration alerts
5. Tax overlay (intentional $0 stub, honesty #5)
6. Attribution (positions, MV-weighted active return, limitations)
7. PM diagnostic — the 7-axiom ℍ_Allocation scorecard + specialist status

---

## 6. Falsifiers (`tests/test_pm_workout.py`)

- `test_pm_workout_runs_all_cohorts` — four cases, each carries every leg
  (risk report, optimizer rebalance, drift, narrative).
- `test_pm_workout_deterministic` — same seed → identical rendered Markdown
  (replayable; no `Date.now`/random in the body).
- `test_pm_workout_single_cohort` — `--cohort` path returns exactly one case.
- `test_render_contains_sections` — the artifact has the ledger + §1–7 markers
  and the persona/track links.
- `test_write_pm_workout_round_trips` — writes a non-empty `.md` to `tmp_path`.

---

## 7. Boundary

- **No new op, no new engine.** The workout is a driver over `pm.advise`
  (S1 — atomic ops unchanged); upgrading a leg = improve the function behind
  its op, never touch the workout.
- **Advisory only.** Never imports a `COMMAND` handler; `session=None`.
- **Errors bubble.** A failing leg re-raises (no `ok=False` swallow — that is
  the e2e *smoke*'s job; the workout is the *report*, and a broken report must
  not look complete).
- **Generated artifact.** `runs/pm_workout/` is gitignored; the repo-root
  `portfolio_manager_workout.md` is written only when `--out` names it.
