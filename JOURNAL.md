# JOURNAL

Build log for Investment Warehouse. Newest entries at top.

---

## 2026-06-30 — rw8: collector import-cycle fix (engineering hygiene)

**Problem:** importing `warehouse.reporting.report_writer` transitively pulled
**46** plane modules (execution/data/research/decision) at module load, because
the package `__init__` eagerly imported `collect`/`writer` and `collect.py`
imported all five planes at module scope. The same fan-out had already produced
a real cycle that the rw5 commit (`2d6be7b`) worked around:

    report_writer.collect → research.risk.adapters.ledger
      → workflows.daily_refresh → messaging.handlers
      → report_writer.writer → report_writer.collect   (loop)

rw5 broke it by *not* importing `HouseholdRiskManifest` from
`adapters.ledger`; instead `_build_household_manifest_from_session` in
`collect.py` returned a bare `tuple[AssetPortfolio, Decimal | None]`. That
inline tuple (plus a duplicated `_household_notional`) was the workaround to
retire.

**Edge cut (root cause):** the smell was a risk *adapter* importing a workflow
*runner*. `research/risk/adapters/ledger.py` no longer imports
`workflows.daily_refresh` at module scope — the import moved into
`_ensure_demo_refresh()` (function scope; the dependency is real but only at
runtime). With that back-edge gone, `collect` can safely depend on the adapter
again.

**Workaround retired:** added a session-backed
`manifest_from_session(session, household_id) -> HouseholdRiskManifest` to
`adapters/ledger.py` (Lib2 — the manifest type and its builders live together;
`build_household_manifest` now delegates to it). `collect._collect_risk_headline`
calls it and reads `manifest.portfolio` / `manifest.notional_usd`, so
`HouseholdRiskManifest` is **restored**; the inline tuple builder and the
duplicated `_household_notional` are deleted.

**Plane-free package import:** the package `__init__` is now a **lazy PEP 562
facade** (`__getattr__` over an `_EXPORTS` name→submodule map; `TYPE_CHECKING`
block preserves static names for mypy/consumers). Every production consumer
(cli, dashboard, `messaging.handlers`, workflows) already imported the
*submodules* directly — the eager re-export was test convenience that forced
the whole plane fan-out on any importer and amplified the cycle. The bare
package import now loads only the facade; `collect.py`/`models.py` keep their
honest module-scope plane imports (Cartography: the integrator map shows what
it depends on; the band-aid would have been scattering those into function
bodies + fragile pydantic deferred-rebuilds).

**Before → after** (acceptance probe):

    import warehouse.reporting.report_writer
    # plane modules in sys.modules:  46  →  0

    import warehouse.workflows.daily_refresh, warehouse.reporting.report_writer
    # acyclic WITHOUT the rw5 workaround:  ok

**Pure import-structure refactor:** no public API/signature changes to
`collect_report_bundle` / `build_and_write_household_reports`; no new
fields/exhibits; errors still bubble. Full gate green — `ruff`, `mypy` (193
files), `pytest` (665 passed).

---

## 2026-06-30 — rw7: comparability columns (prior-period / Δ)

**Problem:** every report-writer exhibit was point-in-time — a performance or
drift figure shipped with no denominator. That violates the report-writer
persona's comparable-figures axiom (Fi2): a number is decision-grade only when
placed against the prior period. The reader had no way to tell a flat quarter
from a moving one.

**Shipped:**

- **`find_prior_bundle(household_id, *, as_of, base=None)`**
  (`reporting/report_writer/collect.py`) — globs `runs/reports/{hh}/**/bundle.json`
  and returns the bundle with the greatest `as_of_date` **strictly earlier**
  than the current `as_of`. Walk-forward safe: a bundle dated on/after the
  current report is never read as "prior" (no lookahead — CLAUDE.md convention).
- **`ReportComparison` + `ComparisonDelta`** (`models.py`) — frozen, registered
  in `frozen_registry.FROZEN_TYPES` (samples + mutation probes; `test_frozen`
  green). `ComparisonDelta` carries `prior`, `abs_delta`, and a fractional
  `pct_delta` (None when prior is zero). The comparison is a lightweight delta
  snapshot, **not** a nested `ReportBundle`, so the prior chain never recurses.
- **Render** (`render.py`) — Exhibit A (performance, both audiences) and Exhibit
  B internal drift table render `Prior` + `Δ` columns. When no prior figure
  exists the cells read `n/a` — never a fabricated `0` (honesty rule §3).
- **Limitations** — the existing generator emits a line when there is no prior
  (first report) or the prior is from a non-adjacent month (gap ≠ 1).
- **Base threading** — `collect_report_bundle` gained an optional `base`;
  `build_and_write_household_reports` passes `repo_root()` so the prior-lookup
  base matches where artifacts are written (no test monkeypatch coupling).
- **Dashboard** — Report writer panel shows `comparison_summary`
  (`vs <prior as_of> (adjacent|non-adjacent) · <snapshot>` or first-report note).

**Tests** (`tests/test_report_writer.py`): most-recent-earlier wins and the
future bundle is never picked; second report shows prior + Δ on perf and drift;
first report renders `n/a` not `$0.00`; a later-dated bundle is never used as
prior; non-adjacent prior emits its limitation; `bundle.json` round-trips the
comparison; panel surfaces the summary. Full gate green (ruff, mypy, 665 pytest).

**Deferred to rw8:** the module-scope cross-plane import cycle in `collect.py`
(unchanged here — `find_prior_bundle` reads only `config`/`Path`).

---

## 2026-06-30 — rw6: advisor approval gate on client delivery

**Problem:** the report writer's external PDF (the client-of-record document)
was gated only by reconciliation breaks — a clean book shipped a PDF with no
named human sign-off. The §1 dataflow's `ADVISOR REVIEW GATE` was hollow. This
is the report-writer persona's costly-signal axiom (T3): the one claim a report
cannot make cheaply is "an advisor stands behind this."

**Constraint discovered:** `approval.create` existed but was hard-wired to
optimizations — `ApprovalRequestRow.optimization_run_id` was NOT NULL with an FK,
and OMS staging joins on it. A document approval could not reuse the row as-is.

**Shipped:**

- **Generalized approval subject** — `ApprovalSubject` enum
  (`optimization` | `report`); `ApprovalRequestRow` gains `subject_type` /
  `subject_id` and `optimization_run_id` is now nullable. **Migration 007**
  (`007_approval_report_subject`, batch mode for SQLite) adds the columns and
  back-fills existing rows as `subject_type=optimization`,
  `subject_id=optimization_run_id`. Round-trips clean on a fresh DB; downgrade
  is intentionally lossy once report approvals exist (NULL run_id can't become
  NOT NULL — fails loudly).
- **Messaging (S1 — no new op):** `approval.create` reused. `ApprovalCreatePayload`
  takes `optimization_run_id` XOR `report_snapshot_id` (a `model_validator`
  raises on both/neither — the gate is the declaration).
- **Gate:** `_attach_external_pdf` now checks recon **then** approval; a report
  with no APPROVED report-subject request blocks with
  `reason=awaiting_advisor_approval`. `approve_and_render_report` records the
  sign-off and *then* renders the PDF — the deliverable cannot exist without a
  named decision. PDF hash lands on the `report_approved` audit row.
- **OMS defense:** `stage_orders_from_approval` raises if an approval has no
  `optimization_run_id` (a report subject must never reach the trade boundary).
- **CLI:** `warehouse report approve --snapshot <id> [--reviewer]`;
  `warehouse approve list` now prints `subject_type=subject_id`.
- **Dashboard:** Report writer panel gained `delivery_state`
  (`delivered` | `awaiting_delivery`) — a freshly built report with no PDF is
  now the normal awaiting-approval state, not an error banner.

**Behavior change:** `report.build` (and the month-end batch) no longer emit a
PDF at build time — they produce review drafts that await per-household advisor
approval. Existing PDF-at-build tests updated to approve first.

**Suite green: 653 passed, 1 skipped (pandoc).** ruff ✓ mypy (193 files) ✓.

---

## 2026-06-30 — Push stability: fast pre-push, Python 3.12 pin, deterministic property tests

**Problem:** `git push` had become slow and intermittently failing. Root cause
was the pre-push hook running the **full** canonical gate (`scripts/ci.sh` with
no arg → lint + format + mypy + full pytest+coverage + `pip install --upgrade
pip` + `pip-audit`). Two structural faults: it was **network-dependent**
(pip-audit → `api.osv.dev`, pip upgrade from PyPI) so any slow/offline moment
failed the push, and it was **fully redundant** with GitHub Actions, which
already runs the same four jobs on every push to `main`. On top of that, two
real defects were tripping the gate.

**Shipped:**

- **Pre-push hook slimmed to fast checks only** (`scripts/git-hooks/pre-push`):
  `ruff check` + `ruff format --check`, **~0.08s, no network**. The full gate
  stays server-side (Actions) and as the end-of-day local command
  (`scripts/ci.sh`). Escape hatch unchanged (`SKIP_CI_HOOK=1`).
- **Python stabilized on 3.12** — local dev had drifted to 3.14.5 while CI and
  mypy only ever ran 3.12. Decimal/float rounding differs across interpreters,
  so tests went red locally but green in CI. Fixes: tightened
  `requires-python` from open-ended `>=3.11` to `>=3.12,<3.13`, added
  `.python-version` (3.12), README now mandates `python3.12 -m venv`. Recreated
  the working venv on 3.12.
- **Oracle tolerance fix** (`tests/test_pm_narrative.py`):
  `test_pm_attribution_oracle_on_hnw_path` compared a re-derived
  `expected_cumulative` against production at exactly one quantum (`1e-6`);
  multi-year `(1+r)**years` compounding rounds independently and drifted ~3e-6.
  New `_ORACLE_TOL = 1e-5` for the oracle re-derivation; the exact algebraic
  recombination identity still asserts at `_QUANTUM`.
- **Deterministic property tests** (`tests/conftest.py`): registered a
  `warehouse` Hypothesis profile (`derandomize=True`, `deadline=None`,
  suppress `too_slow`) and load it unconditionally, so `@given` replays the same
  examples every run — a push never randomly fails on a fresh input Hypothesis
  just discovered. This is the real fix for the "near-singular QP property
  flakes"; with it, the `psd_sigma` vol floor reverted from the band-aid `1e-6`
  back to `1e-8` (restores the original ST6 near-singular stress coverage) and
  passes deterministically.

**Full gate green on 3.12:** lint ✓ format ✓ mypy (193 files) ✓ tests ✓
pip-audit ✓ detect-secrets ✓ (74s — which is exactly why it is no longer on the
per-push path). Fast pre-push path: 0.08s.

**Known follow-up (not addressed):** `reporting/report_writer/collect.py` imports
from all five planes at module scope — the source of the `daily_refresh` import
cycle worked around in the rw5 commit. Stable now, but a recurring-cycle risk.

---

## 2026-06-28 — End-to-end smoke over generated portfolios + IPS

**Shipped:**

- **`run_workflow_smoke` extended** — added the **MV-QP leg** (`mv_rebalance_qp`:
  optimizer v1 po0/po1/po2 — Σw*=1, box-feasible, scenario-robust stress overlay
  ran, μ ex-ante, no trade) and the **PM leg** (`pm_advise`: drives the whole
  `pm.advise` coordinator in-process — risk → policy → attribution → optimizer →
  tax; asserts every leg present, tax held at $0). Each new leg surfaces a raise
  as `ok=False` + detail (loud, not swallowed). v0 TLH and scenario-card legs
  unchanged.
- **`run_e2e_matrix` + `E2eMatrixResult`** — emit one household per cohort
  (`general_hnw` r3, `uhnw_inherited` r3, `founder_executive` r3,
  `concentrated_stress` r4; seed 42, `validate=False`) and run the full smoke on
  each. Portfolio + IPS generated by `emit_synthetic_household`; every leg
  in-process (no DB).
- **Dashboard panel "End-to-end smoke matrix (synthetic)"** on `/research` —
  `dashboard/e2e_data.py` loader + `dashboard/render_e2e.py` (cohort × leg
  pass/fail grid, hover for detail, N/N households-pass badge). Registered in
  `phases.py` (phase 3, live) + `navigation.py` (research panel) → appears in the
  catalog panel registry automatically.
- **Tests** — `tests/integration/test_end_to_end_synthetic.py` (first real test
  under the previously-empty `tests/integration/`): per-cohort pm.advise full
  stack, MV-QP invariants, workflow-smoke leg coverage, matrix all-green +
  determinism. Extended `tests/test_dashboard.py` with the panel render tests.

**Suite green: 399 passed.** Honest note: on bound-determined cohorts
(`general_hnw`) the regime gap is ~0; `founder_executive` / `concentrated_stress`
show non-zero gaps. Tax leg stays $0 across the matrix (honesty #5 not_computed).

**Next:** po1-tax estimates (QuantileTaxEstimator → flips honesty #5), or extend
the matrix to more seeds/rungs.

---

## 2026-06-27 — Synthetic IPS si3 (workflow smokes + scenario card)

**Shipped:**

- **`build_ips_drift_report_from_views`** — session-less drift path in `decision/ips/monitor.py`
- **`lot_positions_from_fixture`** — Shape B → `LotPositionView` adapter
- **`run_workflow_smoke`** — policy monitoring, rebalance/optimizer, scenario fingerprint
- **`ScenarioCard`** — `ips_id`, `binding_constraints_count`; `build_scenario_card` uses
  `emit_synthetic_household`
- **Tests** — `tests/test_synthetic_ips_workflow.py` (cohort matrix + concentrated_stress gates)

**Next:** si4 dashboard binding matrix panel + optional `seed_synthetic_household`.

---

## 2026-06-27 — Synthetic IPS si2 (validate_ips + bundle)

**Shipped:**

- **`validate_ips`** — Shape A sleeve min/max, single-name concentration, liquidity
  tier 1+2 vs unfunded alt commitments (`research/synthetic/ips_validate.py`)
- **`emit_synthetic_household`** — fixture + IPS co-generated from Shape A weights;
  validates before sealing IPS stage hash in provenance
- **`SyntheticHouseholdBundle`** / **`IpsValidationResult`** models
- **Tests** — bundle pass/fail, `concentrated_stress` binding CI gate, mismatch rejection

**Next:** si3 workflow smokes + scenario card IPS metadata.

---

## 2026-06-27 — Synthetic IPS si1 (emit_ips_for_cohort)

**Shipped:**

- **`COHORT_IPS_PRIORS`** — concentration, liquidity floor, allocation band width per cohort
  (`research/synthetic/ips_cohort.py`)
- **`emit_ips_for_cohort`** — builds `InvestmentPolicyStatement` from sampled sleeve weights;
  `concentrated_stress` tight equity ceiling + portfolio concentration range for SDG2 binding path
- **Tests** — `tests/test_synthetic_ips.py` (determinism, priors, binding path)
- **Dashboard** — registry `si1-emit-ips` shipped; smoke check for `ips_emit.py`

**Next:** si2 `validate_ips` + `emit_synthetic_household` bundle.

---

## 2026-06-27 — Synthetic IPS si0a–si0b + contract registry

**Context:** HNW portfolio generator (Shape B, rungs 3–4) shipped without a paired
machine-readable IPS. Research brief and implementation plan defined the gap; risk build
dashboard needed a dedicated track so woven scopes do not drift.

**Shipped:**

- **si0a** — `IpsSleeve` six-sleeve enum; security-master → IPS rollup; drift monitor and
  optimizer use `ips_sleeve_for_position` (no ticker hacks)
- **si0b** — `concentration_limit_pct`, `liquidity_tier_min_pct`, `turnover_budget_pct` on
  `InvestmentPolicyStatement`; migration `005_ips_constraints` (`constraints_json`);
  policy-driven concentration in monitor; `liquidity_vs_ips` in drift alerts
- **Docs** — `docs/research/synthetic_ips.md`, `docs/synthetic_ips_implementation.md`,
  `docs/dev_contract_registry.md`; Cursor rule `.cursor/rules/dev-contract-registry.mdc`
- **Dashboard** — risk build tracker prepends Synthetic IPS pipeline (`si0a → si4`);
  registry rows `si0a`/`si0b` shipped, `si1`–`si4` planned
- **Tests** — `tests/test_ips_sleeves.py`, `tests/test_ips_policy_fields.py`

**Decisions:**

- `IpsSleeve` lives in `decision/ips` (not `research.risk`) — avoids decision→research import;
  string values align with risk `AssetClass` for Shape A composition later
- Risk API boundary unchanged: caller composes `evaluate_risk(manifest)` + IPS drift separately

**Next:** si1 `emit_ips_for_cohort`; si2 `validate_ips` + `emit_synthetic_household` bundle.

---

## 2026-06-24 — Risk API v1.1 HNW compositional generator

**Shipped:**

- `warehouse/research/synthetic/` — cohort profiles, pipeline (lots, alts, calls), Shape B `HouseholdFixture`, Shape A projection
- `risk/synthetic.rung(3..4)` delegates to generator; provenance on `AssetPortfolio` (`cohort_id`, `generator_version`, `seed`, `tension_tags`)
- Scenario cards (Shape C) — `build_scenario_card`, `write_scenario_card`
- Golden matrix extended: `rung3_{none,high_risk}`; fingerprints include provenance
- Tests: `tests/test_hnw_synthetic.py`

**Next:** DB seed adapter from Shape B; tax-vector overlays; full trust-stack graphs.

---

## 2026-06-24 — Risk API v1 overlays & deltas

**Shipped:**

- `ManifestOverlay`, `MetricDelta`, `RiskDeltas` (frozen); `RiskRequest.overlay`
- `overlay.py` — `apply_overlay`, `diff_reports`
- `evaluate_risk(..., assumptions=)` escape hatch for research sweeps
- `synthetic.rung(3..4)` — 5-sleeve HNW-shaped + concentrated equity manifests
- Dashboard deltas panel (`risk_dashboard_demo_overlay`); API `overlay` + `deltas` in response
- Tests: `tests/test_risk_v1.py`

**Deferred:** compositional HNW generator (`warehouse/research/synthetic/`), tax-vector overlays.

---

## 2026-06-24 — Risk API v0c integration

**Context:** v0a envelope and v0b scenario catalog shipped; dashboard still bootstrapped DB, called `load_phase2_dashboard` for side effects, and inlined ledger reads.

**Shipped:**

- `research/risk/adapters/ledger.py` — `build_household_manifest(household_id)` → `HouseholdRiskManifest` (`source="ledger"`, NAV notional)
- Slim `dashboard/risk_data.py` — manifest → `evaluate_risk` → present; no phase2 coupling; domain errors only
- `api.py` — `parse_risk_request`, `evaluate_risk_http`, `risk_result_to_json`; schema `integration` block
- Tests: `tests/test_risk_integration.py` (ledger, HTTP rung2 parity, `KeyError` bubbles)
- Build tracker: contract status **v0c** (5 deliverables shipped)

**Next:** v1 overlays + `RiskDeltas`; HNW compositional generator (rungs 3–4).

---

## 2026-06-24 — Risk API observability & notifications

**Context:** Risk API v0a (`evaluate_risk`, `RiskRequest` / `RiskResult`) and build tracker (`/risk`, `warehouse serve --risk`) were in place; HTTP and dashboard paths still swallowed or under-logged failures.

**Shipped:**

- `research/risk/observability.py` — `log_risk_evaluated` (success, respects `risk_log_inputs`); `record_risk_failure` (structured error log + optional alert)
- `infra/notify/dispatch.py` — `dispatch_risk_alert` for SMTP email and JSON webhook messaging
- Config in `configs/development.toml`: `risk_notify_on_error`, `risk_notify_email_*`, `risk_notify_messaging_*`
- `api.py` — routes through `evaluate_risk` + observability; all HTTP error paths log/notify before returning 400/422; `risk_api_schema()` documents notification keys
- `risk_data.py` — catches only domain errors (`ValueError`, `RiskApiError`, `ValidationError`); programming errors bubble
- Tests: `tests/test_risk_observability.py`; config defaults in `test_config.py`

**Decisions:**

- Notify dispatch failures re-raise — infra errors are not swallowed after a domain failure
- Email/messaging disabled by default in dev; enable via `configs/local.toml` with SMTP host or webhook URL

**Next:** v0b scenarios (`run_scenarios`, `RiskAssumptions`); v0c ledger adapter slimming `risk_data`.

---

## 2026-06-24 — Phase 2 complete

**Delivered:**

- Migration `002_phase2` — ingest, custodian positions, reconciliation breaks, audit log, daily refresh, market prices
- Schwab CSV ingest + `warehouse ingest` / `warehouse refresh` CLI
- Daily refresh workflow (5 steps) with research sandbox file copy
- Reconciliation v0 — custodian vs lot ledger quantity compare
- Dashboard panels: ingest, positions/P&L, recon queue, refresh timeline, audit stream
- `/api/phase2` endpoint

**Next:** Phase 3 tax-aware optimizer and decision plane dashboard.

---

## 2026-06-24 — README CLI reference

**Context:** Documented the `warehouse` CLI for contributors and public-repo clones.

**Added to `README.md`:**

- Setup (`pip install -e ".[dev]"`)
- Dashboard commands (`serve`, `info`) and API URLs
- Database commands (`db bootstrap`, `db upgrade`, `db seed`)
- Dev commands (`pytest`, `ruff`)

**Next:** Phase 2 custodian ingest and positions dashboard.

---

## 2026-06-24 — Phase 1 complete

**Delivered:**

- Alembic `001_initial` — entities, relationships, securities, lots, workflow_definitions
- Demo seed — Smith household graph, 3 securities, 3 lots, 6 workflows
- CLI: `warehouse db upgrade`, `warehouse db seed`, `warehouse db bootstrap`
- Dashboard panels: entity graph, security master search, schema status
- `/api/phase1` JSON endpoint

**Next:** Phase 2 custodian ingest and positions dashboard.

---

## 2026-06-24 — Phase 0 complete

**Delivered:**

- Infra health panel — SQLite, local data, research sandbox, job queue, object store
- `/api/health` endpoint (503 when checks fail)
- GitHub Actions CI — ruff + pytest, no Docker

**Next:** Phase 1 schema design and entity graph views.

---

## 2026-06-24 — Config moved to configs/

**Context:** Application settings are not secrets; belong in version-controlled TOML.

**Decisions:**

- Default config: **`configs/development.toml`** (committed)
- Optional **`configs/local.toml`** for machine overrides (gitignored)
- Removed `.env` / `.env.example`; `WAREHOUSE_CONFIG` env var selects alternate file
- `warehouse.config` loads TOML via pydantic-settings

**Next:** Phase 0 infra health panel (SQLite + local paths).

---

## 2026-06-24 — Early dev: no Docker, public repo

**Context:** Public GitHub repository; defer containerized infra until Phase 4.

**Decisions:**

- Phases 0–3 use **SQLite** + **local filesystem** + **in-process jobs** — no external services
- docker-compose (Postgres, Redis, object store) moved to **Phase 4**
- `.env` gitignored; `configs/development.toml` committed; `configs/local.toml` gitignored
- CI should run pytest + ruff without Docker

**Next:** Phase 0 infra health panel (SQLite + local paths).

---

## 2026-06-24 — Architectural shell

**Context:** Initialized repo from Sharpe founding investment engineer research brief
(`docs/research/sharpe_founding_engineer_brief.md`).

**Decisions:**

- Package name: `warehouse` under `src/`
- Five-plane layout: data, research, decision, execution, reporting
- Build order enforced in docs: ledger + security master → entity graph → optimizer → OMS
- Optimizer v0: heuristics first, MIP upgrade path documented
- Postgres for transactional ledger; Redis for job queue; object store for files
- Research sandbox at `runs/research/` with walk-forward purge config

**Next:** Phase 1 schema design and workflow catalog.

---

## 2026-06-24 — Phase 3: decision plane & optimizer dashboard

**Context:** Phase 3 deliverables from `TODO.md` — IPS drift, tax-aware optimizer v0, advisor approval, backtest harness.

**Shipped:**

- Alembic `003_phase3` — `ips_policies`, `optimization_runs`, `optimization_trades`, `approval_requests`, `backtest_runs`
- TLH heuristics optimizer with explainable trade list and binding constraints
- IPS drift monitor, constraint library (do-not-sell, restricted, IPS min/max)
- Advisor approval workflow with audit trail
- Walk-forward backtest harness with config hash replay
- Dashboard panels + `/api/phase3`; CLI: `warehouse optimize`, `warehouse backtest`, `warehouse approve`
- Demo IPS for Smith household; loss lot for TLH demo

**Next:** Phase 4 — OMS, MIP optimizer, multi-custodian, alternatives, tax depth (SQLite OK).

---

## 2026-06-24 — Phase 4/5 split: product before docker-compose

**Context:** Reviewed whether Phase 4 product work requires docker-compose / Postgres.

**Decision:** Product and infra are decoupled. Phases 0–3 already prove the architecture
on SQLite + local filesystem + in-process jobs (ingest → ledger → reconciliation →
optimizer → approval → backtest, all visible at `warehouse serve`). Phase 4 product
pieces — OMS staging, MIP solver, multi-custodian ingest, alternatives sub-ledger, tax
scenario depth — can ship on the same stack without Docker.

**Postponed to Phase 5:**

- docker-compose (Postgres, Redis, object store)
- SQLite → Postgres migration path
- Redis job queue (replace in-process jobs)
- Postgres RLS on `household_id`

**Pull Phase 5 forward when:** multi-advisor concurrency, tenant isolation, or background
jobs for long MIP/backtest runs — not before Phase 4 dashboard panels ship.

**Next:** Phase 4 product track on SQLite.

---

## 2026-06-24 — Phase 4: execution, alternatives & tax depth

**Context:** Phase 4 product deliverables on SQLite — no docker-compose required.

**Shipped:**

- Alembic `004_phase4` — `staged_orders`, `solver_comparisons`, `alternative_holdings`, `alternative_events`, `tax_scenario_runs`; `optimization_runs.solver_type`
- OMS staging from approved optimizations; order state machine (staged → submitted → filled)
- MIP optimizer stub (lot-discrete) + heuristic comparison panel
- Multi-custodian ingest registry (Schwab + Fidelity parsers)
- Alternatives sub-ledger with marks, capital calls, distributions
- Tax scenario overlays (NIIT, AMT, QSBS exclusion, trust DNI)
- Dashboard panels + `/api/phase4`; CLI: `warehouse order`, `compare-solvers`, `tax-scenario`

**Next:** Phase 5 — docker-compose, Postgres migration, Redis queue.
