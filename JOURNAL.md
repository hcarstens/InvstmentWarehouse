# JOURNAL

Build log for Investment Warehouse. Newest entries at top.

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
