# Code review — Investment Warehouse

**Date:** 2026-06-30
**Reviewer lens:** [Persona of The Critic](docs/heuristics/Persona%20of%20The%20Critic.md) — audit finished work against its *own stated constraints* (CLAUDE.md), steel-man before objecting, calibrate severity, report reproducibly.
**Referent (the brief):** [CLAUDE.md](CLAUDE.md) — dashboard-first, errors-bubble, frozen audit/replay records, walk-forward safety, build order, version-pinning, 79-char line limit.
**Companion:** [docs/qa_test_results_2026-06-30.md](docs/qa_test_results_2026-06-30.md) (qa1–qa8).

**Method:** static read of all 198 source modules across five constraint-anchored audits (error-bubbling, frozen registry, dashboard registry, walk-forward / optimizer, structure) plus a live gate run (`ruff`, `mypy src`, full `pytest`).

---

## Gate run (measured, not assumed)

| Gate | Claim (qa doc) | Measured now | Verdict |
| --- | --- | --- | --- |
| `pytest` | 727 passing | **733 passed**, 2 warnings, 36s | ✓ (suite grew) |
| `ruff check src tests` | clean | **All checks passed** | ✓ |
| `mypy src` | "mypy clean" | **2 errors in 1 file** | ✗ **contradicts the doc** |

The "mypy clean" line in the qa results doc is **false as of this commit** — see C1. This is the load-bearing finding: a continuity break between a shipped status doc and the actual gate (Critic axiom 3).

---

## Severity legend

- **Critical** — wrong portfolio/tax/audit state can occur silently, or a green gate is actually red. The brief's stated nightmare ("prefer a loud failure over a wrong portfolio state").
- **Major** — violates a stated constraint with real blast radius, but latent (no evidence of active breach) or non-runtime.
- **Minor** — local defect, drift, or honesty-by-disclosure gap.
- **Nit** — cosmetic.

---

## Critical

### C1 — `mypy src` is red on `main`; the qa doc claims it is clean
- **Where:** [src/warehouse/decision/pm_workout.py:97](src/warehouse/decision/pm_workout.py#L97)
- **What it does:** `ctx = DispatchContext(session=None)  # type: ignore[arg-type] — pure leg`. The free text `— pure leg` directly after `]` (no second `#`) makes the ignore **malformed**, so mypy (a) rejects the comment (`Invalid "type: ignore" comment [syntax]`) and (b) then surfaces the suppressed error it was meant to hide (`Argument "session" to "DispatchContext" has incompatible type "None"; expected "Session"`). **Both** of mypy's 2 errors trace to this one line.
- **What the constraint requires:** [CI.md](CI.md) runs `mypy src/warehouse` as a full-gate step; the qa doc asserts "mypy clean." A red type gate on `main` is exactly the "looked done but wasn't checked" failure mode qa1–qa8 set out to kill.
- **Reproduce:** `mypy src` → 2 errors in `pm_workout.py`.
- **Fix (mechanical):** `# type: ignore[arg-type]  # pure leg` (second `#`). But see C2 — the underlying type lie is the real issue.
- **Severity:** Critical (broken gate + false documented claim). One-line text fix, but it slipped past pre-push *and* into a status doc.
- **Steel-man:** [memory] pre-push is ruff-only by design; mypy is server-side + end-of-day. So this is "caught later, not never." It is still red right now, and the doc over-claims.

### C2 — `DispatchContext` type does not model the "pure leg"; `None` is forced into a non-Optional `Session`
- **Where:** [src/warehouse/messaging/models.py:56](src/warehouse/messaging/models.py#L56) (`session: Session`, frozen) vs [pm_workout.py:97](src/warehouse/decision/pm_workout.py#L97) (`session=None`).
- **What it does:** The contract docstring says "one `session` per dispatch = one transaction boundary," and the field is non-Optional. The pm-workout "pure leg" genuinely has no DB session, so it passes `None` and silences the type error rather than the type modelling the no-session path. Any handler reached on this path that touches `ctx.session` will `AttributeError` at runtime with no compile-time guard.
- **Constraint:** "Propagate errors; no silent fallbacks." The `type: ignore` is a silent fallback at the type layer.
- **Fix options:** make `session: Session | None` and have handlers assert/raise a typed error when a session is required but absent; or introduce a `PureDispatchContext` variant. Either makes the pure-leg path first-class instead of a suppressed lie.
- **Severity:** Critical (correctness of a frozen, audit-relevant context type), though latent — exercised only by the pm-workout pure leg today.

---

## Major

### M1 — Frozen registry under-covers: 14 already-frozen types are absent from `FROZEN_TYPES`
- **Where:** [src/warehouse/integrity/frozen_registry.py](src/warehouse/integrity/frozen_registry.py) (33 registered) vs frozen-in-code-but-unregistered types.
- **What it does:** `tests/test_frozen.py` iterates `FROZEN_TYPES` and asserts `setattr` raises. Types that are frozen but **unregistered** are never asserted — a future edit dropping `frozen=True` would regress to mutable and the registry test stays green. The brief explicitly says *"Append the type to `FROZEN_TYPES`."*
- **Audit-relevant offenders (register first):**
  - [WashSaleSellEvent](src/warehouse/data/ledger/wash_chains.py#L19) — tax replay record
  - [StockSplitAction](src/warehouse/data/ledger/corporate_actions.py#L37) — corporate-action input to lot basis
  - [CustodianPositionRecord](src/warehouse/data/ingest/schwab_csv.py#L13) — ingest snapshot
  - [RiskAssumptions](src/warehouse/research/risk/assumptions.py#L133) — version-pinned risk priors
  - [StressOverlay](src/warehouse/decision/optimizer/robust.py#L42) — po2 optimizer input
  - [HouseholdRiskManifest](src/warehouse/research/risk/adapters/ledger.py#L26) — risk input manifest
  - (+ `CovarianceResult`, `SleeveRiskState`, `ReportPeriod`, `HnwAssetSpec`, `CohortIpsPriors`, `HarnessCell`, `MutationPlaneResult`, `DashboardPage` — lower audit value but free to register since already frozen)
- **Severity:** Major. The test gives false assurance for 14 types.

### M2 — Audit/replay records that the brief says must be immutable are plain-mutable
- **Constraint:** *"Audit-critical and replay-critical objects must be immutable after construction. Mutation must raise immediately."*
- **Clearest defect — inconsistent twins:** [TaxScenarioResult](src/warehouse/decision/tax/scenarios.py#L36) is a mutable pydantic model (`r.tax_delta = 0` succeeds silently), while its sibling `ReportingTaxResult` (same shape) **is** frozen + registered. Same concept, opposite treatment.
- **Replay fingerprints left mutable:** [ProvenanceManifest](src/warehouse/research/synthetic/models.py#L56) (seed, axiom_set_hash, stage_hashes — the canonical replay fingerprint), [DailyRefreshResult](src/warehouse/workflows/daily_refresh.py#L50) (run record), [ScenarioCard](src/warehouse/research/synthetic/scenario_card.py#L21) (seed/rung/generator_version).
- **Cosmetic-freeze (nested mutability leaks):** these are mutable while embedded as fields of *frozen* wrappers, so the wrapper's freeze is skin-deep —
  - [IpsDriftReport](src/warehouse/decision/ips/monitor.py#L27) inside frozen `ReportBundle`/`AdviceBundle`
  - [PortfolioRiskReport / StressScenarioResult](src/warehouse/research/risk/models.py#L235) inside frozen `RiskResult`
  - [TradeProposal](src/warehouse/decision/optimizer/__init__.py#L15) elements inside frozen `OptimizationResult.trades`
  - [ReconcileResult](src/warehouse/messaging/payloads.py#L175), [EventLogEntry](src/warehouse/messaging/observability.py#L18) (audit-log entry by intent)
- **Severity:** Major (latent — no active mutation found; the guard rail is simply missing). By the brief's own value system ("prefer a loud failure over a wrong portfolio state") `TaxScenarioResult` and `ProvenanceManifest` are arguably Critical-by-policy.
- **Steel-man (correctly excluded):** `ConstraintReport` (incremental builder, discarded), dashboard view-DTOs (`*PageData`, `StatusReport`), and transport payloads (`InFlightRecord`, `*Payload`) are *not* replay records and were not flagged.

### M3 — Two walk-forward guards are defined but never called
- **Where:** [src/warehouse/research/backtest/walk_forward.py:60](src/warehouse/research/backtest/walk_forward.py#L60) (`assert_scenario_observations_not_after`) and [:73](src/warehouse/research/backtest/walk_forward.py#L73) (`assert_series_cutoff`).
- **What it does:** `validate_backtest_walk_forward` wires only `assert_min_backtest_window`, `assert_lots_not_after`, `assert_mark_dates_not_after`. Grep shows **zero call sites** for the other two. A *defined* guard reads as "scenarios/series are protected" when nothing invokes it — exactly the "walk-forward in name only" pattern qa6 was meant to close, one layer deeper.
- **Reproduce:** `grep -rn assert_scenario_observations_not_after src/` → definition only.
- **Severity:** Major, not Critical — the harness has no scenario-replay or path-slice leg *today*, so there is no live leakage point to bypass (forward-provisioning). Flag it so "guard exists" never silently means "guard runs."
- **Forward-looking caveat (latent):** [list_lot_positions](src/warehouse/data/ledger/views.py#L59) outer-joins `MarketPriceRow` with **no `as_of_date` predicate**. It is benign *only* because `MarketPriceRow` PK is `security_id` alone (one mark per security). The day that table becomes a time series, this join silently selects the latest mark with no cutoff, and `assert_mark_dates_not_after` validates the dates present but not *which* mark is chosen. Leave a comment / test pinning the single-row assumption.

### M4 — Plane business logic is orchestrated from `dashboard/*_data.py`
- **Constraint (Libraries/Cartography):** dashboard is a *consumer* of plane state; computation lives in the plane package. Several loaders invoke engines directly:
  - [optimizer_data.py](src/warehouse/dashboard/optimizer_data.py) → `run_mv_rebalance` (decision-plane QP solve)
  - [risk_data.py](src/warehouse/dashboard/risk_data.py) → `evaluate_risk` (research engine)
  - [synthetic_ips_data.py](src/warehouse/dashboard/synthetic_ips_data.py) → `emit_synthetic_household` + `run_workflow_smoke` (orchestrates the synthesis pipeline)
- **Why it matters:** the engine entry points now have two callers (plane + dashboard) with the dashboard one untested by plane tests; a CLI/headless path can't reuse the dashboard's orchestration. Prefer a thin plane-level facade the dashboard calls read-only.
- **Severity:** Major (architecture / collocation), no runtime defect.
- **Steel-man:** `phase{2,3,4}_data.py` (cross-plane phase orchestration) and `reporting_performance_data.py` (calls `build_household_performance_report` and just shapes it) are correctly *thin* and were not flagged.

---

## Minor

- **m1 — Backtest `tax_delta` is structurally always `Decimal("0")`.** [harness.py:88-90](src/warehouse/research/backtest/harness.py#L88): `after_tax_return` and `baseline_after_tax_return` are the *same* expression, so the persisted delta is identically zero (the comment admits "until harvest replay lands"). Honest in code, but the persisted audit column is a vacuous rationale field. Either populate it or mark it `not_computed` so consumers don't read 0 as "no tax impact."
- **m2 — QP `RebalanceProposal` carries no tax-delta-vs-baseline.** [rebalance.py:134](src/warehouse/decision/optimizer/rebalance.py#L134) uses a `ZeroTaxEstimator` identity; the constrained-MV leg reports `objective_value`/risk contributions but no tax line. The optimizer-rationale rule ("tax delta vs baseline") is satisfied **by disclosure** (honesty matrix marks it `not_computed`) and by the lot-level TLH leg, which does carry it. Compliant-by-disclosure; noted so the gap is on record.
- **m3 — Tax scenario panel marked `live` while the tax engine is stubbed to `$0`.** [phases.py:128](src/warehouse/dashboard/phases.py#L128) vs [TODO.md](TODO.md) ("kept at `$0` on purpose"). Not mislabeled under the brief (panel exists, wired across all 4 registries, renders real-if-zero output, stub documented) — but the live/stub semantics of *this* panel deserve a maintainer's eye since "live" + "$0" can read as a real zero.
- **m4 — `ruff` E501 ignore drifts past what CLAUDE.md authorizes.** [pyproject.toml](pyproject.toml) per-file-ignores comment says *"CLAUDE.md allows >79 in render_\*.py / server.py"* then also exempts `phases.py` **and** `status.py` (non-render modules) — the config contradicts its own cited justification. CLAUDE.md only authorizes `render_*.py` / `server.py`. Separately, real >79 lines survive in non-exempt files (e.g. [config.py:82](src/warehouse/config.py#L82), [cli.py:81](src/warehouse/cli.py#L81)) because they are string literals `ruff format` can't break — so "79 chars, no `# noqa: E501`" is not fully true in practice. Either align CLAUDE.md with the real exemption list, or wrap the offending strings.
- **m5 — `ruff target-version = "py311"` while `requires-python = ">=3.12,<3.13"`.** [pyproject.toml:63](pyproject.toml#L63). Lint targets an older Python than the project pins ([memory]: 3.12-only). Bump to `py312`.
- **m6 — `workflow_smoke.py:75` downgrades `WalkForwardError` to a status record.** [workflow_smoke.py:75](src/warehouse/research/synthetic/workflow_smoke.py#L75) catches the WF error into `ok=False`/`detail` rather than re-raising. Acceptable (it is a smoke-*reporter* and the failure is surfaced on the panel), but it is the one place a `WalkForwardError` is caught and converted to data — fine as long as no caller treats `ok` as advisory.
- **m7 — God files.** [cli.py](src/warehouse/cli.py) (747 LOC) and [infra/db/seed.py](src/warehouse/infra/db/seed.py) (652 LOC) violate single-responsibility; decompose `cli.py` into subcommand modules and extract `seed.py` fixture builders. `frozen_registry.py` (569) and `pm_workout.py` (546) are large but cohesive — acceptable.

## Nit

- **n1 — Phase-numbered vs plane-named vocabulary.** `dashboard/phase{1,2,3,4}_data.py` are cross-plane deliverables named by milestone, not plane (controlled-vocabulary drift, HLib4). Consider a `dashboard/phases/` subdir to signal "phase orchestration, not plane data."
- **n2 — `PytestCollectionWarning` x2** on `TestingReport` (`dashboard/testing_data.py:81`) — pytest tries to collect a `Test*`-prefixed pydantic model. Rename (`PanelTestingReport`) or add `__test__ = False` to silence.

---

## What holds up (steel-manned positives — calibrated, not flattery)

These were probed for defects and found sound; recording them keeps the severity signal honest.

1. **Error-bubbling is exemplary — 0 violations across all 29 `except Exception` sites.** Every catch either re-raises with context (`err.add_note(op/correlation_id/household_id)` in [messaging/core.py:71](src/warehouse/messaging/core.py#L71); audit-write-then-`raise` in [ingest/runner.py:91](src/warehouse/data/ingest/runner.py#L91) and [daily_refresh.py:261](src/warehouse/workflows/daily_refresh.py#L261)) or is a legitimate isolation boundary that surfaces the failure (dashboard `error` fields → HTTP 503 in [server.py:213](src/warehouse/dashboard/server.py#L213); `record_exception_panel`; `record_risk_failure` → HTTP 500). No bare `except`, no swallowed errors. This is the hardest CLAUDE.md rule and it is met.
2. **Dashboard registry is consistent across all four locations.** phases.py (39 panels) == navigation.py panel set exactly; no duplicate ownership; all 8 plane routes (`/ /data /research /decision /execution /reporting /infra /risk`) wired and reachable; all 13 `render_*` modules reach a page; **no panel marked `live` is unwired or raises `NotImplementedError`.** Every live loader runs real DB/engine code over seeded/synthetic households (sample data permitted by the brief until ingest is live).
3. **Optimizer rationale is complete and populated** — every `TradeProposal` carries lots touched + `rationale`; `OptimizationResult` always carries `estimated_tax_delta` + `binding_constraints`; QP leg carries `binding_bounds`/`risk_contributions`/`policy_drift`. Feasibility and sleeve-mapping failures **raise loudly** (`OptimizerInfeasibleError`, `OptimizerMappingError`) with explicit "not silently clipped" messaging.
4. **Version-pinning for audit replay holds.** `Settings` frozen; `tax_config_version="2026.01"` / `optimizer_config_version="2026.06"` stamped on every result; `RiskAssumptions` frozen + `model_version`; backtest `_config_hash` folds tax version + rates + purge into the persisted run.
5. **Build order respected.** Ledger + security master + entity graph + reconciliation all present; OMS ([execution/oms](src/warehouse/execution/oms/service.py)) and reconciliation ([execution/reconciliation](src/warehouse/execution/reconciliation/service.py)) both exist with positions→optimizer→OMS dependency direction. No evidence of OMS shipping ahead of reconciliation. (Execution/Reporting top-level `__init__.py` are thin by correct design — logic lives in subpackages, not a missing plane.)
6. **Suite is green and grew** — 733 passing, ruff clean.

---

## Verdict (Critic)

The system **largely honors its own brief** — error-bubbling, dashboard wiring, optimizer rationale, version-pinning, and build order all survive adversarial reading, several exemplary. The defects cluster, predictably, at **the edges the brief itself names as load-bearing but does not yet fully enforce**:

- a **red mypy gate on `main`** that a status doc claims is clean (C1/C2),
- **immutability declared but not enforced** for ~14 unregistered frozen types and several mutable audit/replay records, including frozen wrappers with mutable innards (M1/M2),
- a **walk-forward guard that exists but never runs** (M3),
- and **plane logic leaking into the dashboard layer** (M4).

None of these is presently *breaching* state silently — they are **missing guard rails on the exact failure modes qa1–qa8 were written to prevent**, one layer deeper than the qa slices reached. Highest-value next actions, in order: **(1) fix C1** (red gate), **(2) `frozen=True` + register `TaxScenarioResult` / `ProvenanceManifest` and the M1 audit types**, **(3) wire or relocate the two dead walk-forward guards.**
