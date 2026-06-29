# TODO — Investment Warehouse

Phased deliverables aligned with Sharpe founding investment engineer priorities.
See `docs/research/sharpe_founding_engineer_brief.md` for full context.

**Dashboard-first rule:** Every phase ships a runnable dashboard view. No phase closes
without something new visible at `warehouse serve`. The catalog at `/` is the entry point;
operational panels live on plane pages (`/data`, `/research`, `/decision`, `/execution`,
`/reporting`, `/infra`). The dashboard is the living status report — it reflects real
system state (data, jobs, breaks, proposals), not static docs.

**Early dev (public repo):** No Docker through Phase 4. Use SQLite + local filesystem +
in-process jobs so `warehouse serve` and `pytest` run with zero external services.
Postgres, Redis, and docker-compose move to **Phase 5** (prod parity, not a gate on
product work). Non-secret settings live in **`configs/`** (committed); use
`configs/local.toml` (gitignored) for machine-specific overrides only.

---

## Phase 0 — Shell + dashboard foundation ✓

**Dashboard at run:** Catalog (`/`) — platform overview, phase roadmap, plane readiness, workflow catalog, infra summary, orchestrator gate.

- [x] Repository architecture and package layout
- [x] `configs/`, `requirements.txt`, `tests/`, `CLAUDE.md`, `.claude/`
- [x] **Dashboard shell** — `warehouse serve` → status report (phases, planes, workflows)
- [x] CI: pytest + ruff on push (no Docker services in CI)
- [x] **Dashboard:** infra health panel (SQLite, local paths; optional external services shown as skipped)

---

## Phase 1 — Weeks 1–4: Discovery, schema & data model views ✓

**Dashboard at run:** `/data` — entity graph explorer, security master table, schema/migration status.

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

**Dashboard at run:** `/data` (ingest, positions) · `/execution` (recon, refresh) · `/infra` (audit log).

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

**Dashboard at run:** `/decision` (IPS, optimizer, approval) · `/research` (backtests).

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

**Dashboard at run:** `/execution` (staged orders, solver) · `/data` (custodian, alts) · `/reporting` (tax scenarios).

**Architecture note:** Phase 4 product work ships on the same stack as Phases 0–3 — SQLite,
local filesystem, in-process jobs. Docker-compose and Postgres are **not** prerequisites;
they are deferred to Phase 5 for prod parity (concurrency, RLS, async jobs, object store).

Backend:
- [x] **OMS / trade staging and routing** — approval → staged order → execution state machine
- [x] **Full MIP optimizer** (Gurobi / CPLEX) — lot-discrete solves behind feature flag
- [x] **Multi-custodian ingest** — parser registry, per-custodian normalization
- [x] **Alternatives sub-ledger** — manual marks, capital calls, distributions
- [x] **Tax scenario depth** — AMT, NIIT, QSBS, trust DNI overlays on optimizer/backtest *(UI wired; engine stubbed to zero — see loose threads below)*

---

## Loose threads (post-messaging)

- [x] **Reconcile `as_of_date` gate** — `reconcile_ingest` opens a break when custodian file `as_of_date` ≠ ledger market-price `as_of_date` (stale file no longer reconciles clean).
- [ ] **Tax scenario engine (estimate)** — Replace the zero-stub in `evaluate_tax_scenario` with threshold-aware after-tax math (Tax Analyst heuristic: cliff-effect navigation, not flat additive NIIT/AMT). **Parallel / non-blocking** — deliberately held while we stress-test the PM flow with `tax → $0` (see Portfolio Manager block). Sub-notes:
  - [ ] Pin NIIT/AMT phase-outs and income thresholds to `tax_config_version`
  - [ ] Model income character and entity splits (not a single rate × unrealized gains)
  - [ ] Falsifier tests against known household fixtures

### Portfolio Manager (pm0–pm2) ✓ — `docs/portfolio_manager_implementation.md`

- [x] **pm0 — narrative + 7-axiom checklist** — `score_pm_axioms → PmNarrative` over the 4 legs; `axiom_5` honest `not_computed`; `AdviceBundle`/`PmNarrative` frozen + registered.
- [x] **pm1 — working set + rebalance advisory** — `build_working_set`, `run_rebalance_advisory` (`ledger.positions → pm.advise`, advisory-only); HNW rung-3 smoke.
- [x] **pm2 — dashboard + registry** — advisory panel (axiom strip + specialist badges + `tax: stub`); `portfolio_manager` track + `warehouse.decision.pm` boundary registered.
- [x] **Advisory bundle panel (full)** — `AdviceBundle` presentation keyed by `correlation_id`: headline, ℍ_Allocation axiom strip, specialist liveness badges.
- [ ] **Tax leg stub → live** — flips `evaluate_tax_scenario` to real numbers; **does not change the `pm.advise` contract**. Gated on the tax estimate engine above, *not* on PM. Kept at `$0` on purpose so synthetic portfolios + IPS can exercise the whole flow.

### Portfolio Analyst (pa0–pa2) — **shipped** — `docs/portfolio_analyst_implementation.md`

Analyst leg is **live** today for drift + concentration (`policy.check`) plus the pa0–pa2 depth
(attribution + residual, thesis + kill criteria, NPA flags). It feeds the genuinely hard
downstream problem (optimization) — the **next milestone**. Keep tax at `$0` throughout so the
analyst → optimizer signal can be stress-tested on synthetic books.

- [x] **pa0 — attribution** — P&L residual vs benchmark / policy; explainable per-sleeve contribution (Portfolio Analyst heuristic: Goodhart vigilance, no faked scores). Shipped: `attribution.evaluate`, residual decomposition, PM 5th leg, attribution residuals panel.
- [x] **pa1 — kill criteria** — pre-committed exit rules per thesis; surface breaches as alerts (not autonomous sells). Shipped: `PositionThesis`/`KillCriteria`/`KillBreach`, `evaluate_kill_criteria` (pure, alerts-only), checkpoint-1 wiring, synthetic theses, kill-criteria watch panel.
- [x] **pa2 — non-performing-asset flags** — sustained drawdown vs cost, stale alt marks, missed capital calls, IPS liquidity breach (cross-ref open question #13 — resolved v0: rule thresholds version-pinned to `analyst_config_version`, flags feed the approval gate only, not optimizer constraints). Shipped: `flag_non_performing` (pure, reason-coded, alerts-only), `NpaFlag`/`NpaFlags` frozen, NPA panel across positions/alternatives/manifest, `tests/test_analyst_npa.py`.
- [ ] **Unlocks → Portfolio Optimization v1** — plan: [`docs/portfolio_optimization_implementation.md`](docs/portfolio_optimization_implementation.md). Constrained mean-variance QP in sleeve-weight space on the risk plane's real Σ — pure + advisory (target w\* + Δw + risk contributions behind `optimizer.propose`, **no new op**, no trades staged). The hard problem; only as good as the analyst signal feeding it. **Shipped: po0 + po1-turnover + po1-tax seam + po2** (`solve_qp` projected-gradient/capped-simplex, raising `_SLEEVE_TO_RISK`, frozen `RebalanceProposal`/`OptimizationResult`, hard `‖Δw‖₁ ≤ τ` ROUTE B step, $0 `ZeroTaxEstimator` seam, `high_risk` crisis-Σ stress overlay; honesty #8 flipped, #5 stays `not_computed`; "MV rebalance" panel with base-vs-stress; falsifiers `tests/test_optimizer_{qp,mapping,rebalance,turnover,tax_seam,robust}.py`). **Open scope:** po1-tax estimates + po3 (sub-bullets below).
  - [ ] **po1-tax estimates (later)** — behind the shipped $0 `TaxEstimator` seam (§14 Addendum C): `QuantileTaxEstimator` (best-guess drag by holding period / class / lot gain) → **flips honesty #5 → computed** + validate; then `LLMTaxEstimator` (QSBS, trust DNI, AMT edge cases) **last**. Same upgrade-path ladder as ROUTE B → ROUTE A. Also: optional analyst `active_return`/NPA μ-tilt (advisory, never a hard constraint).
  - [ ] **po3 — lot-discrete MIQP (documented upgrade path)** — `x_l` sell/hold binaries + wash-sale graph; needs a commercial solver (Gurobi/CPLEX), out of scope under Phases 0–4. Stays doc-only until a solver is sanctioned (`mip.py`/`compare.py` are the benchmark stubs).
  - [ ] **po1 limitation — ROUTE B → ROUTE A upgrade** — replace the budget-scaled convex step with the true L1-constrained MV optimum (Dykstra alternating projection onto box ∩ simplex ∩ L1-ball, Duchi et al. 2008). Fixes the box-breaching drift below; B is a feasible-direction step, not the argmax.
  - [ ] **po1 limitation — box-breaching `w_current` drifts turnover off τ** — when current weights violate the IPS box, `w_budget` is projected back onto box ∩ simplex so `Σw=1`/feasibility hold, and `‖Δw‖₁` can exceed τ (e.g. demo rung-3: capped 0.217 → 0.157 vs τ=0.15). Exact on τ only when `w_current` is box-feasible. Resolved by ROUTE A.
  - [ ] **po1 limitation — annual-vs-per-rebalance τ horizon** — `ips.turnover_budget_pct` is documented "annual" but po1 applies it as a per-rebalance `‖Δw‖₁` cap (labelled, not silently reconciled). Needs a horizon/turnover-accounting model to amortize the annual budget across rebalances.
  - [ ] **po1 convention note — `‖Δw‖₁` is two-way turnover** — `Σ|Δw| = buys + sells` (since `ΣΔw=0`); one-way = `‖Δw‖₁/2`. Confirm budget semantics (one-way vs two-way) with the IPS contract before client use.
- [x] **End-to-end smoke over generated portfolios + IPS** — `run_workflow_smoke` extended with an **MV-QP leg** (optimizer v1 po0/po1/po2 — Σw*=1, box-feasible, scenario-robust stress overlay ran, μ ex-ante, no trade) and a **`pm.advise` leg** (whole coordinator in-process: risk → policy → attribution → optimizer → tax; every leg present, tax $0). `run_e2e_matrix` emits one household per cohort (`general_hnw`/`uhnw_inherited`/`founder_executive`/`concentrated_stress`, seed 42, `validate=False`) and runs the full smoke — portfolio + IPS generated by `emit_synthetic_household`, every leg in-process (no DB). Dashboard panel **"End-to-end smoke matrix (synthetic)"** on `/research` (cohort × leg pass/fail grid; phases.py phase 3 live + navigation research panel → catalog registry). Falsifiers: `tests/integration/test_end_to_end_synthetic.py` (per-cohort pm.advise full stack, MV-QP invariants, leg coverage, matrix all-green + determinism), `tests/test_dashboard.py` panel render. Proves generation feeds every plane. **Next:** more seeds/rungs, or wire the matrix into the "Review all portfolios" batch below.
- [ ] **Review all portfolios** — Household-book review workflow (PM orchestrator): run across every household when material inputs change. Triggers and scope:
  - [ ] **Tax change** — `tax_config_version` bump, overlay rule change, or lot realization event → re-run `tax.scenario` / after-tax compare per book (`docs/portfolio_manager_implementation.md`).
  - [ ] **Month-end reporting** — positions reconciled, marks fresh, period close → `report.build` (when reporting plane ships) + IPS drift + exception queue snapshot per household. **Partial (rw3):** `report.build` month-end fan-out via `workflows.month_end.run_month_end_reporting_batch` — full PM batch (`pm.advise` + risk delta + tax-change triggers per household) remains future.
  - [ ] **Risk changes** — manifest or assumption regime change, new stress pack, material position move → `risk.evaluate` + delta vs prior snapshot; surface on dashboard with `correlation_id`.
  - [ ] Batch orchestration: `ledger.positions` → `pm.advise` per household; failures propagate (no silent skip); advisor queue for books that fail any leg.

---

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
13. **Flag non-performing assets** — *Resolved v0 (pa2).* `flag_non_performing` ships reason-coded rules (sustained drawdown vs cost, stale alt mark, missed capital call, IPS liquidity breach) with thresholds version-pinned to `analyst_config_version`; flags are pure/advisory and feed the **approval gate only** (never optimizer constraints in v0), surfaced on a dedicated NPA panel across positions/alternatives/manifest. Still open: advisor-tagged (manual) NPA status alongside the rule-derived flags, and whether a later version promotes selected flags to optimizer constraints.
14. **Compiled raw data has secondary value** — Ingested custodian files, lot-level ledger, and derived panels (positions, risk manifest, IPS drift) are primary operational inputs — but the *compiled* household dataset also has secondary value: research replay, walk-forward backtests, scenario packs, model priors, and advisor analytics. How should the platform treat compiled data as a product asset (versioning, fingerprinting, sandbox isolation from prod client data) vs ephemeral pipeline output? Scope: what may be exported or reused, retention, and boundaries so secondary use never leaks proprietary allocations/horizons or undermines audit replay.

---

## Phase 5 — Prod infra: docker-compose & Postgres upgrade

**Dashboard at run:** `/infra` — Postgres, Redis, object store health (replacing skipped stubs).

**When to pull this forward:** multi-advisor concurrency, household RLS, background jobs
for long MIP/backtest runs, or pilot deployment — not before product panels in Phase 4 ship.

Infrastructure:
- [ ] **docker-compose** — Postgres, Redis, object store for local prod parity
- [ ] **Postgres migration path** — SQLite dev ledger → managed Postgres (Alembic dialect path)
- [ ] **Redis job queue** — replace in-process jobs for optimizer, backtest, ingest batches
- [ ] **Object store** — custodian files, research artifacts, audit exports
- [ ] **Postgres RLS** — row-level security on `household_id` for multi-tenant pilot
