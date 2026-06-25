# TODO — Investment Warehouse

Phased deliverables aligned with Sharpe founding investment engineer priorities.
See `docs/research/sharpe_founding_engineer_brief.md` for full context.

**Dashboard-first rule:** Every phase ships a runnable dashboard view. No phase closes
without something new visible at `warehouse serve`. The dashboard is the living status
report — it reflects real system state (data, jobs, breaks, proposals), not static docs.

**Early dev (public repo):** No Docker through Phase 4. Use SQLite + local filesystem +
in-process jobs so `warehouse serve` and `pytest` run with zero external services.
Postgres, Redis, and docker-compose move to **Phase 5** (prod parity, not a gate on
product work). Non-secret settings live in **`configs/`** (committed); use
`configs/local.toml` (gitignored) for machine-specific overrides only.

---

## Phase 0 — Shell + dashboard foundation ✓

**Dashboard at run:** Platform overview, phase roadmap, plane readiness, workflow catalog, infra health.

- [x] Repository architecture and package layout
- [x] `configs/`, `requirements.txt`, `tests/`, `CLAUDE.md`, `.claude/`
- [x] **Dashboard shell** — `warehouse serve` → status report (phases, planes, workflows)
- [x] CI: pytest + ruff on push (no Docker services in CI)
- [x] **Dashboard:** infra health panel (SQLite, local paths; optional external services shown as skipped)

---

## Phase 1 — Weeks 1–4: Discovery, schema & data model views ✓

**Dashboard at run:** Entity graph explorer, security master table, schema/migration status.

Backend:
- [x] **Workflow catalog** — owner, inputs, outputs, SLA (onboarding through reporting)
- [x] **Entity graph v0** — Person, Household, Trust, LLC, Account, Custodian edges
- [x] **Security master v0** — CUSIP/ISIN/ticker, asset class, tax character, wash-sale groups
- [x] **Lot ledger schema** — cost basis, holding period, wash-sale chains
- [x] Alembic migrations against **SQLite** (local file under `data/`; Postgres later)

Dashboard panels (each phase item maps to a visible panel):
- [x] **Entity graph view** — household → accounts → custodians (interactive or tabular)
- [x] **Security master browser** — search/filter instruments and tax attributes
- [x] **Schema status** — applied migrations, table row counts, last migration time

---

## Phase 2 — Weeks 5–12: Vertical slice & positions dashboard ✓

**Dashboard at run:** Live positions, ingest pipeline, reconciliation exceptions, daily P&L.

Backend:
- [x] **Single custodian ingest** — file parser → normalized positions
- [x] **One household end-to-end** — ingest → ledger → daily P&L → household view
- [x] **Daily refresh workflow** — reconcile → update lots → corporate actions → exception queue
- [x] **Audit trail** — who changed what, when
- [x] **Research sandbox** — isolated from prod client data

Dashboard panels:
- [x] **Ingest status** — last run, files processed, errors, row counts
- [x] **Positions & lots** — account × instrument × lot with cost basis and unrealized P&L
- [x] **Reconciliation queue** — open breaks, age, resolution actions
- [x] **Daily refresh timeline** — custodian → reconcile → lots → corp actions (step status)
- [x] **Audit log stream** — recent changes with actor and resource

---

## Phase 3 — Weeks 13–26: Decision plane & optimizer dashboard ✓

**Dashboard at run:** IPS drift, optimizer proposals, approval queue, backtest outcomes.

Backend:
- [x] **Tax-aware optimizer v0** — TLH heuristics + greedy rebalance on sample portfolios
- [x] **Constraint library** — IPS min/max, wash-sale, restricted lists, do-not-sell lots
- [x] **Explainable trade list** — lots, binding constraints, tax delta vs baseline
- [x] **Sim / backtest harness** — historical prices + lot state → trades → after-tax outcome
- [x] **IPS monitoring** — drift vs strategic allocation, concentration
- [x] **Advisor approval workflow** — staged orders, sign-off gates
- [x] Pilot reconciliation flows and exception handling

Dashboard panels:
- [x] **IPS drift monitor** — current vs target weights, concentration alerts
- [x] **Optimizer proposals** — trade list, rationale, estimated tax delta vs baseline
- [x] **Approval queue** — pending / approved / rejected with reviewer and timestamps
- [x] **Backtest results** — after-tax return, tax delta, config hash, snapshot ID
- [x] **Constraint binding report** — which IPS / tax rules are active per household

---

## Phase 4 — Execution, alternatives & tax depth ✓

**Dashboard at run:** Staged orders, solver comparison, multi-custodian ingest, alternatives
sub-ledger, tax scenario panel.

**Architecture note:** Phase 4 product work ships on the same stack as Phases 0–3 — SQLite,
local filesystem, in-process jobs. Docker-compose and Postgres are **not** prerequisites;
they are deferred to Phase 5 for prod parity (concurrency, RLS, async jobs, object store).

Backend:
- [x] **OMS / trade staging and routing** — approval → staged order → execution state machine
- [x] **Full MIP optimizer** (Gurobi / CPLEX) — lot-discrete solves behind feature flag
- [x] **Multi-custodian ingest** — parser registry, per-custodian normalization
- [x] **Alternatives sub-ledger** — manual marks, capital calls, distributions
- [x] **Tax scenario depth** — AMT, NIIT, QSBS, trust DNI overlays on optimizer/backtest

Dashboard panels:
- [x] **Staged orders** — pending / routed / filled with approval linkage
- [x] **Solver comparison** — heuristic vs MIP: trades, tax delta, runtime
- [x] **Custodian selector** — ingest and positions filtered by custodian
- [x] **Alternatives panel** — alt marks, capital calls, distributions by entity
- [x] **Tax scenario panel** — what-if overlays on household after-tax outcome

---

## Scope cuts (v0)

- Single custodian, public markets (equities / ETFs) until Phase 4 multi-custodian
- Manual entry for alternatives (Phase 4 sub-ledger)
- Heuristics before mixed-integer optimization (Phase 4 MIP upgrade)
- **No Docker in Phases 0–4** — SQLite + local files; public GitHub repo
- App settings in **`configs/development.toml`** (not secrets); optional `configs/local.toml`

---

## Open questions (clarify before Phase 4)

1. Execution model — in-house trading, custodian API, or advisor-only recommendations?
2. System of record — wealth graph authoritative vs custodian overlay?
3. Pilot scope — internal household vs external UHNW families?
4. Build vs buy — native ledger vs Addepar / Orion / Tamarac?
5. Compliance — RIA/fiduciary obligations, trade surveillance, regulatory reporting, and audit retention requirements?
6. Income optimization without principle drawdown — many family offices have recurring income obligations for family members; how should the optimizer target yield/dividends vs selling lots?
7. Synthetic portfolio data for stress testing — generate realistic household portfolios and price paths for backtest and scenario panels without client data?
8. Security layer and logging — authentication, authorization, audit-grade request logging, and secrets handling for pilot deployment?
9. Heuristic agents & report writer — how should agent-driven workflows (IPS drift triage, recon exceptions, optimizer narrative) and the heuristic report writer integrate with `warehouse serve`, the audit trail, and advisor approval gates without bypassing frozen, replayable outputs?
10. **Agent for IPS compliance monitoring** — Explore an agent that watches household state against digitized IPS constraints and narrative governance (`docs/research/ips.md`): strategic allocation bands, concentration limits, restricted lists, liquidity floors, ESG exclusions. How does it complement (not replace) rule-based Phase 3 drift monitoring? Scope: interpret prose IPS sections vs enforce machine-readable rules, triage alerts, explain breaches, escalate to advisor approval — never autonomous trades. When scoped, ship a dashboard panel alongside the existing IPS drift monitor.
11. **LLM first pass for tax scenarios** — Use an LLM to draft initial tax-scenario overlays (AMT, NIIT, QSBS, trust DNI, entity structure) from household state + IPS before the deterministic engine in `decision/tax/scenarios.py` runs. How to pin inputs, validate outputs, and keep advisor review + frozen audit replay?
12. **Portfolio risk: Fermi vs measurable** — For UHNW households, how much of total portfolio risk is defensible order-of-magnitude (Fermi) estimation — illiquid alts, concentrated equity, trust/entity structure, tax path dependency — vs directly measurable from positions and prices? Where should the dashboard show confidence bands vs hard metrics?

---

## Phase 5 — Prod infra: docker-compose & Postgres upgrade

**Dashboard at run:** Infra health shows Postgres, Redis, and object store live (replacing
skipped stubs); schema status reflects Postgres migration path.

**When to pull this forward:** multi-advisor concurrency, household RLS, background jobs
for long MIP/backtest runs, or pilot deployment — not before product panels in Phase 4 ship.

Infrastructure:
- [ ] **docker-compose** — Postgres, Redis, object store for local prod parity
- [ ] **Postgres migration path** — SQLite dev ledger → managed Postgres (Alembic dialect path)
- [ ] **Redis job queue** — replace in-process jobs for optimizer, backtest, ingest batches
- [ ] **Object store** — custodian files, research artifacts, audit exports
- [ ] **Postgres RLS** — row-level security on `household_id` for multi-tenant pilot
