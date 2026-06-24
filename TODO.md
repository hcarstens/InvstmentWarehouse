# TODO — Investment Warehouse

Phased deliverables aligned with Sharpe founding investment engineer priorities.
See `docs/research/sharpe_founding_engineer_brief.md` for full context.

**Dashboard-first rule:** Every phase ships a runnable dashboard view. No phase closes
without something new visible at `warehouse serve`. The dashboard is the living status
report — it reflects real system state (data, jobs, breaks, proposals), not static docs.

**Early dev (public repo):** No Docker. Use SQLite + local filesystem + in-process jobs
so `warehouse serve` and `pytest` run with zero external services. Postgres, Redis, and
docker-compose move to Phase 4. Non-secret settings live in **`configs/`** (committed);
use `configs/local.toml` (gitignored) for machine-specific overrides only.

---

## Phase 0 — Shell + dashboard foundation ✓

**Dashboard at run:** Platform overview, phase roadmap, plane readiness, workflow catalog, infra health.

- [x] Repository architecture and package layout
- [x] `configs/`, `requirements.txt`, `tests/`, `CLAUDE.md`, `.claude/`
- [x] **Dashboard shell** — `warehouse serve` → status report (phases, planes, workflows)
- [x] CI: pytest + ruff on push (no Docker services in CI)
- [x] **Dashboard:** infra health panel (SQLite, local paths; optional external services shown as skipped)

---

## Phase 1 — Weeks 1–4: Discovery, schema & data model views (current)

**Dashboard at run:** Entity graph explorer, security master table, schema/migration status.

Backend:
- [ ] **Workflow catalog** — owner, inputs, outputs, SLA (onboarding through reporting)
- [ ] **Entity graph v0** — Person, Household, Trust, LLC, Account, Custodian edges
- [ ] **Security master v0** — CUSIP/ISIN/ticker, asset class, tax character, wash-sale groups
- [ ] **Lot ledger schema** — cost basis, holding period, wash-sale chains
- [ ] Alembic migrations against **SQLite** (local file under `data/`; Postgres later)

Dashboard panels (each phase item maps to a visible panel):
- [ ] **Entity graph view** — household → accounts → custodians (interactive or tabular)
- [ ] **Security master browser** — search/filter instruments and tax attributes
- [ ] **Schema status** — applied migrations, table row counts, last migration time

---

## Phase 2 — Weeks 5–12: Vertical slice & positions dashboard

**Dashboard at run:** Live positions, ingest pipeline, reconciliation exceptions, daily P&L.

Backend:
- [ ] **Single custodian ingest** — file parser → normalized positions
- [ ] **One household end-to-end** — ingest → ledger → daily P&L → household view
- [ ] **Daily refresh workflow** — reconcile → update lots → corporate actions → exception queue
- [ ] **Audit trail** — who changed what, when
- [ ] **Research sandbox** — isolated from prod client data

Dashboard panels:
- [ ] **Ingest status** — last run, files processed, errors, row counts
- [ ] **Positions & lots** — account × instrument × lot with cost basis and unrealized P&L
- [ ] **Reconciliation queue** — open breaks, age, resolution actions
- [ ] **Daily refresh timeline** — custodian → reconcile → lots → corp actions (step status)
- [ ] **Audit log stream** — recent changes with actor and resource

---

## Phase 3 — Weeks 13–26: Decision plane & optimizer dashboard

**Dashboard at run:** IPS drift, optimizer proposals, approval queue, backtest outcomes.

Backend:
- [ ] **Tax-aware optimizer v0** — TLH heuristics + greedy rebalance on sample portfolios
- [ ] **Constraint library** — IPS min/max, wash-sale, restricted lists, do-not-sell lots
- [ ] **Explainable trade list** — lots, binding constraints, tax delta vs baseline
- [ ] **Sim / backtest harness** — historical prices + lot state → trades → after-tax outcome
- [ ] **IPS monitoring** — drift vs strategic allocation, concentration
- [ ] **Advisor approval workflow** — staged orders, sign-off gates
- [ ] Pilot reconciliation flows and exception handling

Dashboard panels:
- [ ] **IPS drift monitor** — current vs target weights, concentration alerts
- [ ] **Optimizer proposals** — trade list, rationale, estimated tax delta vs baseline
- [ ] **Approval queue** — pending / approved / rejected with reviewer and timestamps
- [ ] **Backtest results** — after-tax return, tax delta, config hash, snapshot ID
- [ ] **Constraint binding report** — which IPS / tax rules are active per household

---

## Phase 4 — Later (explicitly deferred)

**Dashboard at run:** Execution and alternatives panels (stub until backend ships).

Infrastructure (deferred from early dev):
- [ ] docker-compose — Postgres, Redis, object store for local parity with prod
- [ ] Postgres migration path from SQLite dev ledger
- [ ] Redis job queue (replace in-process jobs)

Product:
- [ ] OMS / trade staging and routing → **staged orders panel**
- [ ] Full MIP optimizer (Gurobi / CPLEX) → **solver comparison panel**
- [ ] Multi-custodian support → **custodian selector on ingest/positions**
- [ ] Alternatives sub-ledger → **alt marks, capital calls, distributions panel**
- [ ] AMT, NIIT, QSBS, trust DNI depth → **tax scenario panel**

---

## Scope cuts (v0)

- Single custodian, public markets (equities / ETFs)
- Manual entry for alternatives
- Heuristics before mixed-integer optimization
- Dashboard uses demo/sample data until Phase 2 ingest is live
- **No Docker in Phases 0–3** — SQLite + local files; public GitHub repo
- App settings in **`configs/development.toml`** (not secrets); optional `configs/local.toml`

---

## Open questions (clarify before Phase 3)

1. Execution model — in-house trading, custodian API, or advisor-only recommendations?
2. System of record — wealth graph authoritative vs custodian overlay?
3. Pilot scope — internal household vs external UHNW families?
4. Build vs buy — native ledger vs Addepar / Orion / Tamarac?
