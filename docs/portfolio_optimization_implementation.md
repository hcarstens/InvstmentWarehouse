# Portfolio Optimization — Implementation Plan

**Status:** **planned** — next milestone after Portfolio Analyst pa0–pa2 (shipped).
This PR ships the **plan doc only** (plus the §10 cross-refs); **no production code** this
window. The existing suite stays green (`pytest`, no behavior change).
**Date:** 2026-06-28
**Owner:** decision plane / `warehouse.decision.optimizer` (existing package — upgrade in place)
**Inputs:** [`research/portfolio_optimization.md`](research/portfolio_optimization.md) (DHA run, credence 0.70 — after-tax utility > unconstrained max-Sharpe; Σ regime-conditional; weight ≠ risk; μ estimation error dominates MV theory),
[`heuristics/Portfolio Optimization.md`](heuristics/Portfolio%20Optimization.md) (PO1–PO8),
[`heuristics/Mental Model of The Portfolio Manager.md`](heuristics/Mental%20Model%20of%20The%20Portfolio%20Manager.md) (axiom 6 — gate the binding-constraint count),
[`portfolio_analyst_implementation.md`](portfolio_analyst_implementation.md) (the structural template + the analyst signal that gives the optimizer its objective/constraint set; Addendum A.1 enum-join trap),
[`messaging_protocol.md`](messaging_protocol.md) (§5 catalog, S1 atomic-op rule — `optimizer.propose` already exists),
[`research/hnw_portfolios.md`](research/hnw_portfolios.md) (rung ladder, cohorts),
[`dev_contract_registry.md`](dev_contract_registry.md) (new `portfolio_optimization` track)

---

## 1. Principle — propose a defensible target weight vector, never trade

Portfolio optimization is the **weight-vector allocation engine** the analyst plan named as
"the genuinely hard downstream problem." Its job is to map the household's current sleeve weights
**w** to a **target weight vector w\*** that is efficient on the risk plane's real Σ and feasible
inside IPS bounds, and to report the rebalance **Δw = w\* − w** with its binding constraints and
risk-contribution shares. It is **pure and advisory**: it produces targets and a delta, it
**never stages trades and never auto-executes** — the human approval gate dominates (CLAUDE.md).

The optimizer is only as good as the analyst signal feeding it
(`portfolio_analyst_implementation.md` §1): pa0–pa2 shipped the **objective and constraint
inputs** — attribution residual (`active_return`), kill breaches, NPA flags. v1 consumes those
**advisorily** (a μ tilt, a surfaced alongside) but **never converts a flag into a hard
constraint** (§6 invariant; resolves open question #13 the analyst way).

| Layer | Package / `op` | Role | Kind |
| --- | --- | --- | --- |
| **Portfolio Manager** | `decision.pm` → `pm.advise` | Whole-book coordinator; nest-dispatches the optimizer leg | EVALUATE composite |
| **Optimizer (v0, live)** | `decision.optimizer` → `optimizer.propose` | TLH ranking + IPS min/max **breach flags** on class weights | EVALUATE |
| **Optimizer (v1, this plan)** | `decision.optimizer` → `optimizer.propose` (**same op**) | **Constrained MV QP** → target w\* + Δw + risk contributions | EVALUATE |

```text
PORTFOLIO MANAGER                          OPTIMIZER (sleeve-weight, pure, advisory)
pm.advise ──┬── risk.evaluate              optimizer.propose
            ├── policy.check                 → OptimizationResult
            ├── attribution.evaluate           .trades            (TLH harvest — v0, unchanged)
            ├── optimizer.propose  ◄── UPGRADE  .rebalance         ◄── NEW additive field (po0)
            │      → run_tax_aware_optimizer        → target_weights w*, delta_w Δw,
            │        (TLH) + run_mv_rebalance(QP)      binding_bounds, risk_contributions
            └── tax.scenario  (held at $0 — flow-test enabler; after-tax μ = not_computed)
```

**Why the engine upgrades behind the existing op:** `optimizer.propose` is already nest-dispatched
by `pm.advise` into `AdviceBundle.proposal`. Upgrading the engine **behind** the op (an additive
`OptimizationResult.rebalance` field) keeps `test_pm_no_new_ops` (`pm.* == {pm.advise}`) and the
"no coordinator op" discipline green — **no new atomic op for po0** (§6).

---

## 2. The honesty rule — computable vs `not_computed`

The DHA failure modes are explicit: *stale μ/Σ → unstable optima*, *pre-tax MV on an after-tax
mandate*, *illiquids treated as daily-rebalance assets*. po0 takes those literally about its **own
output** — every quantity it cannot compute is `not_computed` in the report and on the dashboard,
never faked. μ is labelled an **ex-ante class assumption**, never a forecast or realized alpha
(PO6; mirrors the analyst's "active vs ex-ante class assumption" honesty, A.3).

| # | Optimization quantity | Computed from | Status |
| --- | --- | --- | --- |
| 1 | **Constrained MV target w\*** (`max w'μ − (λ/2)w'Σw`, `1'w=1`, `w_min ≤ w ≤ w_max`) | real Σ + μ over sleeve weights | **po0 — computable** |
| 2 | **Δw = w\* − w_current** | sleeve weights from `ips_sleeve_for_position` | **po0 — computable** |
| 3 | **Risk-contribution shares** `RC_i` | `portfolio_covariance(...).pct_variance_contributions` at w\* | **po0 — computable** |
| 4 | **Binding IPS bounds** at w\* | `AllocationTarget.min_weight/max_weight` | **po0 — computable** |
| 5 | After-tax effective μ (TLH / asset-location / gain-deferral) | no tax engine — tax leg held at `$0` | **`not_computed`** (deferred po1) |
| 6 | Turnover-cost penalty `‖Δw‖₁ ≤ τ` | `turnover_budget_pct` exists; **not enforced in po0** | **reported, not constrained** (po1) |
| 7 | Lot-discrete sell/hold binaries `x_l` + wash-sale graph | MIQP, no external solver allowed | **`not_computed`** (deferred po3) |
| 8 | Regime-conditional / scenario-robust Σ | only base-regime Σ; stress is a separate overlay | **`not_computed`** (deferred po2) |
| 9 | Factor-model Σ (n > 50 sleeves) | class-block Σ only (6 sleeves) | **`not_computed`** (out of scope) |
| 10 | OOS validation of μ/Σ | no signal/screen pipeline (shared gap w/ analyst checkpoint 4) | **`not_computed`** |
| 11 | Risk-free blend / CML leverage (PO3), Kelly sizing (PO4) | no cash-leverage or edge-estimate layer | **`not_computed`** (out of scope) |

**Stated limitations (surfaced in the report + dashboard, not hidden):**

- **μ is an ex-ante assumption** (`CLASS_EXPECTED_RETURN`), not a forecast — PO6: optimizers
  amplify input error and overweight high-μ sleeves that are often noise. po0's defense is the
  **box constraints `w_min ≤ w ≤ w_max` as diversification floors/caps** (PO6 last sentence), not
  μ-shrinkage; shrinkage toward an equilibrium prior is deferred and labelled as such.
- **Base-regime Σ only** (PO7 non-stationarity): correlations spike toward 1 in crises and the
  diversification benefit collapses exactly when needed. po0 optimizes on the normal-regime prior
  and **says so**; the scenario-robust overlay is po2, not a silent assumption.
- **Weight ≠ risk** (research §"Multi-Asset Specifics" #2): equal sleeve weights carry unequal
  `RC_i`. po0 therefore reports `RC_i` next to w\*, so the advisor reads risk space, not just
  weight space.
- **Illiquids sit outside daily Δw** (research #5): alternatives are a sleeve in **w** but cannot
  be traded daily. po0's Δw on the alternatives sleeve is **advisory-only and flagged**; po0 does
  not assume it is executable (failure mode "illiquids treated as daily-rebalance assets").

---

## 3. What is computable today (po0 QP mechanics)

The risk plane already ships a real Σ and μ **at the sleeve level**:

- **μ:** `assumptions_for("base").class_expected_return` — `dict[research.risk.AssetClass, Decimal]`.
- **Σ entries:** `class_annual_vol[c]` and `pairwise_correlation(c_i, c_j)` give
  `Σ_ij = σ_i · σ_j · ρ_ij` (the exact `cov[i][j]` formula inside `portfolio_covariance`).
- **Current w:** `ips_sleeve_for_position(pos)` rolls each `LotPositionView` to an `IpsSleeve`;
  market-value weights are already assembled this way in `run_tax_aware_optimizer`.
- **Bounds:** `ips.allocation_targets[].{min_weight, max_weight, target_weight}`, keyed by `IpsSleeve`.

```text
universe S   = sleeves in positions  ∪  sleeves in ips.allocation_targets   (ordered, IpsSleeve)
w_current[s] = Σ_{pos∈s} market_value / total_mv                            (s ∈ S)
w_min[s], w_max[s] = AllocationTarget(s).min_weight / .max_weight           (default [0,1] if no target — §A.3)
μ[s]   = class_expected_return[ risk_class_for(s) ]                         (explicit map — §A.1, RAISES if unmapped)
Σ[i,j] = vol[risk_class_for(s_i)] · vol[risk_class_for(s_j)] · ρ(.. , ..)   (build once — §A.2)

maximize   f(w) = wᵀμ − (λ/2)·wᵀΣw
subject to 1ᵀw = 1 ,  w_min ≤ w ≤ w_max
solve      projected-gradient ascent + capped-simplex projection (§A.2), λ + tol pinned
report     w* (target), Δw = w* − w_current, binding bounds, RC = pct_variance_contributions(w*)
```

**Walk-forward safe:** Σ/μ are the as-of base-regime priors; no realized-return lookahead
(CLAUDE.md). The QP reads only `as_of` marks and version-pinned assumptions.

**This is a first-cut constrained MV QP**, labelled as such: class-block Σ (not factor), base
regime (not regime-conditional), pre-tax μ (after-tax overlay deferred). The corrected, stable
algorithm + the enum mapping live in **§A (Addendum)** — read that as the po0 spec.

---

## 4. Scope — what ships vs deferred

### In scope (po0)

| Item | Rationale |
| --- | --- |
| `run_mv_rebalance(w_current, ips, assumptions, *, settings) → RebalanceProposal` (constrained MV QP) | The optimizer value-add — efficient w\* on real Σ inside IPS bounds (PO2) |
| Additive `OptimizationResult.rebalance: RebalanceProposal \| None` | Upgrade **behind** `optimizer.propose`; **no new op** (S1) |
| Explicit total `_SLEEVE_TO_RISK` map that **raises** on an unmapped sleeve (§A.1) | No silent zero-μ; errors bubble (CLAUDE.md) |
| Pure-Python QP solver (projected-gradient + capped-simplex projection) | No external solver (CLAUDE.md Phases 0–4) |
| `optimizer_config_version` + `risk_aversion_lambda` + QP tolerances in `config.py` | Audit replay (mirrors `analyst_config_version` / `pm_axiom_config_version`) |
| Feasibility guard: infeasible box∩simplex **raises** (no silent clip) | No default-on-failure (CLAUDE.md) |
| Freeze + register `RebalanceProposal` **and** `OptimizationResult` (not frozen today) | Audit/replay-critical |
| Optimizer rebalance panel: target-vs-current w, Δw, binding bounds, `RC_i` | Dashboard-first |
| Falsifier tests + new `portfolio_optimization` track rows | Contract discipline |

### Deferred

| Item | Slice | Why |
| --- | --- | --- |
| Turnover penalty `‖Δw‖₁ ≤ τ` (PO8) | po1 | po0 **reports** turnover; constraining it needs the L1 term + tax cost model |
| TLH / asset-location / gain-deferral **after-tax** overlay | po1 | No tax engine (tax leg `$0`); overlay runs **inside** IPS bounds, not as substitute |
| Scenario-robust stress overlay (worst-case over `STRESS_SCENARIOS`, PO7) | po2 | Base-regime Σ only in po0; robust objective is a distinct optimization |
| Lot-discrete MIQP + wash-sale graph (`x_l` binaries) | po3 | The CLAUDE.md "documented upgrade path to full MIP"; no commercial solver |
| μ-shrinkage toward equilibrium prior (PO6) | po1+ | po0 defends with box constraints only; shrinkage labelled deferred |
| Risk-free blend / CML leverage (PO3), Kelly sizing (PO4) | out of scope | No cash-leverage or edge-estimate layer |
| Analyst flags (NPA / kill / residual) as **hard constraints** | never (v1) | Advisory → approval gate only; may inform a μ tilt, never a binding constraint (§6) |
| Autonomous execution of Δw | never | Advisory; advisor decides and stages (human gate) |

---

## 5. Migration slices — PR sequence + acceptance

No package sprawl: the upgrade lands **in** `warehouse.decision.optimizer` — new `rebalance.py`
(QP) and `qp.py` (pure solver) beside the existing `heuristics.py` / `mip.py` / `compare.py` /
`runner.py`. The handler `_optimizer_propose` stays a thin wrapper; it gains the QP call.

### po0 — constrained mean-variance QP *(~1 PR)*

**Goal:** `optimizer.propose` returns a target sleeve-weight vector + Δw + risk contributions, on
real Σ inside IPS bounds; PM carries it. Advisory — no trades staged.

| Task | File(s) |
| --- | --- |
| `RebalanceProposal` (frozen): `target_weights`, `current_weights`, `delta_w` (per `IpsSleeve`), `binding_bounds`, `risk_contributions`, `objective_value`, `config_version` | `decision/optimizer/models.py` *(new)* |
| `solve_qp(mu, sigma, w_min, w_max, *, lam, tol, max_iters)` — projected-gradient + capped-simplex projection; feasibility guard raises | `decision/optimizer/qp.py` *(new)* |
| `run_mv_rebalance(...)`: assemble universe, `_SLEEVE_TO_RISK` (raises on unmapped, §A.1), build Σ once (§A.2), solve, roll up `RC_i` via `portfolio_covariance` at w\* | `decision/optimizer/rebalance.py` *(new)* |
| Additive `OptimizationResult.rebalance`; `_optimizer_propose` calls `run_mv_rebalance` and attaches it | `decision/optimizer/__init__.py`, `messaging/handlers.py` |
| `optimizer_config_version`, `risk_aversion_lambda`, `qp_tolerance`, `qp_max_iters` | `config.py` |
| Freeze + register `RebalanceProposal` **and** `OptimizationResult` | `integrity/frozen_registry.py`, `tests/test_frozen.py` |
| Rebalance panel (target-vs-current w, Δw, binding bounds, `RC_i`) + loader | `dashboard/optimizer_data.py` *(new)*, `dashboard/render_phase3.py`, `dashboard/phases.py` |

**Acceptance:**

- **Zero-Δ probe** (PASS falsifier): a household already at the unconstrained interior optimum →
  `‖Δw‖∞ ≈ 0`, `binding_bounds == []` (current == optimum; §9).
- A household breaching a sleeve max → w\* clips to `w_max`, that bound appears in `binding_bounds`,
  Δw moves **toward** feasibility (mirrors `test_concentrated_stress_optimizer_documents_binding`).
- **Monotone in λ:** raising `risk_aversion_lambda` lowers `wᵀΣw` at w\* (more risk-averse → lower
  portfolio variance) — a property test, no magic numbers.
- **Unmapped sleeve raises** `OptimizerMappingError` — never a silent zero-μ (§A.1).
- **Infeasible bounds raise** (`Σ w_min > 1` or `Σ w_max < 1`) — never a silent clip.
- `result.rebalance is not None`; **no `TradeProposal` is emitted from the rebalance path** (advisory).
- `test_pm_no_new_ops` still green (`pm.* == {pm.advise}`; `optimizer.*` unchanged).
- `pytest tests/test_frozen.py` green (`OptimizationResult`, `RebalanceProposal` immutable).

### po1 — turnover budget + after-tax (TLH) overlay *(~1 PR)*

**Goal:** constrain `‖Δw‖₁ ≤ τ` (PO8) and run the TLH/asset-location overlay **inside** IPS bounds.

| Task | File(s) |
| --- | --- |
| L1 turnover constraint from `ips.turnover_budget_pct`; rebalance on threshold drift, not calendar (PO8) | `decision/optimizer/rebalance.py` |
| After-tax effective μ (TLH harvest value, gain deferral) once the tax leg goes live — overlay, not substitute | `decision/optimizer/rebalance.py`, `tax.scenario` |
| Optional μ tilt from analyst `active_return` / NPA (advisory weight, **not** a hard constraint) | `decision/optimizer/rebalance.py` |

**Acceptance:** Δw respects `‖Δw‖₁ ≤ τ`; flip 5 (after-tax μ) from `not_computed` to computed only
when the tax leg is live; analyst tilt changes w\* but never forces a bound.

### po2 — scenario-robust stress overlay *(~1 PR)*

**Goal:** complement base-regime MV with a worst-case-over-`STRESS_SCENARIOS` objective (PO7).

| Task | File(s) |
| --- | --- |
| Robust objective: penalize / report w\* under crisis-correlation Σ (`2008`, `2020`, `2022` packs) | `decision/optimizer/robust.py` *(new)* |
| Surface the regime-conditional gap: base-MV w\* vs stress-robust w\* side by side | `dashboard/render_phase3.py` |

**Acceptance:** flip honesty-matrix #8 from `not_computed` to computed; stress-robust w\* differs
from base-MV w\* on the concentrated fixture (PO7 — diversification collapses under crisis ρ).

### po3 — lot-discrete MIQP (documented upgrade path) *(deferred — doc only)*

The CLAUDE.md "documented upgrade path to full MIP." `x_l` sell/hold binaries + wash-sale graph =
MIQP, which needs a commercial solver (Gurobi/CPLEX) — **out of scope under Phases 0–4 / zero
external services**. `mip.py` / `compare.py` remain the benchmark stubs; po3 stays a documented
target, not code, until a solver is sanctioned.

---

## 6. Protocol & boundary invariants — acceptance matrix

| Invariant | Source | Test |
| --- | --- | --- |
| Optimizer engine upgrades **behind** `optimizer.propose` — **no new atomic op** | messaging S1 | `test_pm_no_new_ops` (existing), `test_optimizer_op_surface` |
| QP is pure — never reads `ctx.session` for mutation, never persists | messaging §4.1 | `test_rebalance_pure` |
| Rebalance is **advisory** — produces w\*/Δw only, **stages no trade, auto-executes nothing** | human-gate (CLAUDE.md) | `test_rebalance_no_persist`, `test_rebalance_emits_no_trade` |
| Analyst flags (NPA/kill/residual) are **never hard constraints** — advisory μ tilt at most | analyst open-Q#13 v0 | `test_analyst_flags_not_optimizer_constraints` (mirrors `test_npa_no_persist`) |
| Unmapped sleeve → **raise**, never silent zero-μ | CLAUDE.md errors-bubble | `test_sleeve_mapping_raises` |
| Infeasible box∩simplex → **raise**, never silent clip | CLAUDE.md no-default-on-failure | `test_qp_infeasible_raises` |
| μ labelled **ex-ante class assumption**, never "forecast"/"alpha" | PO6 + analyst A.3 | `test_mu_not_named_forecast` |
| `risk_aversion_lambda` + QP tolerances **pinned** to `optimizer_config_version` | audit replay | `test_optimizer_config_pinned` |
| Binding-constraint set stays **legible/few** (PM axiom 6) | PM mental model 6 | `test_binding_bounds_legible` |
| Walk-forward — Σ/μ as-of, base regime, no lookahead | CLAUDE.md | `test_rebalance_walk_forward` |
| PM op surface unchanged (`pm.* == {pm.advise}`) | PM §6 | `test_pm_no_new_ops` (existing) |

**No new op needed for po0** — the QP is reached through the existing `optimizer.propose` handler;
adding an op would be reflexive sprawl (S1). po2's robust overlay also stays behind the same op.
If a future slice genuinely needs an atomic op (e.g. a standalone `optimizer.frontier` trace), it
must be justified here first — none is justified through po3.

---

## 7. Test plan summary

| File | Covers |
| --- | --- |
| `tests/test_optimizer_qp.py` | solver correctness: zero-Δ probe, binding bounds, λ-monotonicity, infeasibility raise, feasibility of `1ᵀw=1` |
| `tests/test_optimizer_rebalance.py` | universe union, `_SLEEVE_TO_RISK` raise, Σ built once, `RC_i` rollup, advisory (no trade staged) |
| `tests/test_optimizer_mapping.py` | explicit sleeve→risk map total + raises; **regression for the silent-success trap** (§A.1) |
| `tests/test_pm_workflow.py` | *(extend)* `AdviceBundle.proposal.rebalance` present on demo + HNW rung 3 |
| `tests/test_synthetic_ips_workflow.py` | *(extend)* concentrated_stress binding bounds via QP (alongside the existing v0 assertion) |
| `tests/test_dashboard.py` | *(extend)* rebalance panel: target-vs-current w, Δw, binding bounds, `RC_i` |
| `tests/test_frozen.py` | `OptimizationResult`, `RebalanceProposal` immutable (+ falsifier) |

**CI gate:** QP correctness (zero-Δ + binding + monotone) + mapping raises + advisory no-persist +
config pinned + PM op-surface unchanged.

---

## 8. Dependencies & build order

```text
risk Σ/μ (portfolio_covariance, assumptions_for) + IPS allocation_targets + analyst pa0–pa2   [shipped]
  └─ po0 (constrained MV QP; advisory w*/Δw/RC behind optimizer.propose)        [planned — NEXT]
       └─ po1 (turnover ‖Δw‖₁≤τ + after-tax TLH overlay inside IPS bounds)      [planned]
            └─ po2 (scenario-robust stress overlay — PO7)                        [planned]
                 └─ po3 (lot-discrete MIQP — documented upgrade path)            [deferred — doc only]

Held on purpose (non-blocking):
  tax estimate engine  →  flips after-tax μ (#5) not_computed → live (po1)
```

**Depends on:** risk covariance plane (Σ/μ), IPS model (`allocation_targets`), the live
`optimizer.propose` op, analyst pa0–pa2 (advisory inputs).
**Does not depend on:** tax estimate engine (held `$0`), any external/commercial solver, valuation
engine, Phase 5 infra.

---

## 9. HNW fixture matrix (acceptance households)

| Fixture | Source | Exercises |
| --- | --- | --- |
| Demo seed | `DEMO_HOUSEHOLD_ID` (DB bootstrap) | End-to-end rebalance panel + PM `proposal.rebalance` |
| `general_hnw` rung 3 | `project_to_asset_portfolio` → 5-sleeve weights | Interior QP, multi-sleeve Δw, `RC_i` spread |
| `concentrated_stress` rung 4, **seed 42** | SDG2 negation, **`validate=False`** | Binding sleeve-max bounds (extends `test_concentrated_stress_optimizer_documents_binding`) |
| `founder_executive` rung 4, **seed 11** | same | Concentrated single-name → binding concentration / sleeve cap |
| **zero-Δ probe** | crafted household already at the constrained optimum | `‖Δw‖∞ ≈ 0`, `binding_bounds == []` — the **PASS falsifier** |

`founder_executive` / `concentrated_stress` **fail IPS validation at seed 42** — emit with
`validate=False` (exactly as pa0–pa2 do). Demo uses DB bootstrap; the synthetic rungs run the
in-process path (`project_to_asset_portfolio` / `lot_positions_from_fixture`) — **no DB** for the
panel loader (mirrors `analyst_data.py` / `npa_data.py`).

---

## 10. Doc updates on ship

| Doc | Update |
| --- | --- |
| [`dev_contract_registry.md`](dev_contract_registry.md) | New `portfolio_optimization` track row(s) po0–po3; `warehouse.decision.optimizer` boundary note (engine upgraded behind `optimizer.propose`; QP advisory, no new op) |
| [`../TODO.md`](../TODO.md) | Flip "Unlocks → Portfolio Optimization v1" to **in-progress**; link this plan doc |
| [`../CLAUDE.md`](../CLAUDE.md) | **Add the missing heuristics-table row** for [`Portfolio Optimization.md`](heuristics/Portfolio%20Optimization.md) (PO1–PO8) — currently absent (doc gap) |
| [`research/portfolio_optimization.md`](research/portfolio_optimization.md) | Cross-ref this plan; note po0 implements the constrained-MV-QP row of "InvestmentWarehouse today" |
| [`portfolio_analyst_implementation.md`](portfolio_analyst_implementation.md) | Note: optimizer consumes analyst signal **advisorily** (open question #13 v0 — flags never become hard constraints) |
| [`messaging_protocol.md`](messaging_protocol.md) | §5 note: `optimizer.propose` return enriched (additive `rebalance`), **no new op** |

---

## 11. Self-review

### Strengths

- **Computable first cut on real inputs** — w\*/Δw/`RC_i` come from the shipped Σ/μ
  (`portfolio_covariance`, `CLASS_EXPECTED_RETURN`, `pairwise_correlation`), not a stub; the QP is
  a genuine constrained MV program, not a heuristic relabelled.
- **Honest by construction** — after-tax μ, regime-conditional Σ, lot-discreteness, OOS validation
  are each `not_computed` with a named slice, never faked; μ is labelled an ex-ante assumption
  (PO6), echoing the analyst's A.3 discipline.
- **Minimal surface** — engine upgrades **behind** `optimizer.propose`; no new op; `OptimizationResult`
  gains one additive optional field; PM contract additive.
- **Advisory/acting split preserved** — w\*/Δw are proposals; nothing stages or executes (human gate).
- **Code-grounded blocker caught** — §A inverts the analyst's KeyError trap into the more dangerous
  *silent-success* trap and specifies the explicit raising map.

### Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Enum join silently mis-prices μ/Σ if `IpsSleeve`/`AssetClass` values drift (§A.1) | Explicit `_SLEEVE_TO_RISK` that **raises**; `test_optimizer_mapping.py` is a regression guard |
| Reusing `portfolio_covariance` for the QP gradient (it returns variance, **not** Σ) | Build Σ once from `class_annual_vol` + `pairwise_correlation`; use `portfolio_covariance` only to report `RC_i` at w\* (§A.2) |
| QP overweights high-μ noise (PO6) | Box constraints as diversification floors/caps; μ-shrinkage deferred + labelled, not silently applied |
| Base-regime Σ misleads in crisis (PO7) | Limitation surfaced in report + dashboard; scenario-robust overlay scoped as po2 |
| Freezing `OptimizationResult` breaks an existing mutator | po0 audits `runner.py` / `compare.py` mutation sites before flipping `frozen=True`; `test_frozen.py` falsifier proves immutability |
| Decimal↔float boundary in the solver | Solve in `float64`, quantize w\* back to `Decimal` within `qp_tolerance`; **re-assert `1ᵀw=1` within `AssetPortfolio`'s 0.0001 validator** before reporting (§A.2) |
| Infeasible IPS bounds silently clipped | Feasibility guard raises (`test_qp_infeasible_raises`) |
| Analyst flags creep into hard constraints | §6 invariant + `test_analyst_flags_not_optimizer_constraints` (open-Q#13 v0) |

### Verdict

**Ready to execute** starting with po0 (constrained MV QP). Estimated **3 implementable PRs**
(po0–po2) + po3 documented. Critical path: **po0 → po1 → po2**. po0 alone turns the optimizer from
a breach-flagger into a target-weight proposer — the milestone the analyst plan pointed at.

---

## 12. Addendum A — po0 enum-join + Σ-reuse correction (pre-po0 spec)

The analyst plan's Addendum A.1 caught a hard `KeyError` from joining `class_expected_return` on the
wrong enum. **The same class of bug exists here — but its failure mode is inverted and *worse*.**
This is the spec po0 implements.

### A.1 The join silently succeeds — which is more dangerous than a KeyError

Three enums touch the QP:

| Quantity | Enum | Members / values |
| --- | --- | --- |
| IPS bounds `allocation_targets[].asset_class` | `decision.ips.sleeves.IpsSleeve` | `equity, fixed_income, commodities, fx, alternatives, cash` |
| Σ / μ keys (`class_expected_return`, `class_annual_vol`) | `research.risk.models.AssetClass` | `equity, fixed_income, commodities, fx, alternatives, cash` |
| Position class `LotPositionView.security_asset_class` | `data.security_master.AssetClass` | `equity, fixed_income, cash, alternative` (**singular**), `etf` |

`IpsSleeve` and `research.risk.AssetClass` are **value-identical `StrEnum`s** — same six members,
same lower-snake string values (aligned by design; the `sleeves.py` docstring says *"six-sleeve
rollup aligned with risk `AssetClass`"*). Both are `str` subclasses, so:

```python
research.risk.AssetClass.EQUITY == IpsSleeve.EQUITY          # True  (str.__eq__ on "equity")
hash(IpsSleeve.EQUITY) == hash(research.risk.AssetClass.EQUITY)  # True  (str hash)
class_expected_return[IpsSleeve.EQUITY]                      # SUCCEEDS — no KeyError
```

So unlike the analyst `_SEC_TO_RISK` case (which `KeyError`-ed loudly on `"alternative"` ≠
`"alternatives"` and unmapped `ETF`), the naive `μ[ips_sleeve]` join here **silently resolves** via
`StrEnum` string-hash equality. That is the trap: it works on today's demo and would pass review,
then **mis-prices μ/Σ the instant either enum's string values drift** (e.g. an IPS rename
`fx → currency`, or a risk split `alternatives → {private_equity, real_estate}`) — and it would do
so by **returning a wrong number, not raising**. CLAUDE.md forbids exactly this silent-fallback
class.

**Spec:** po0 does **not** rely on coincidental `StrEnum` cross-equality. It adds an explicit,
total map that **raises** on any unmapped sleeve — so future drift fails loudly:

```python
# decision/optimizer/rebalance.py
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.research.risk.models import AssetClass as RiskClass

_SLEEVE_TO_RISK: dict[IpsSleeve, RiskClass] = {
    IpsSleeve.EQUITY: RiskClass.EQUITY,
    IpsSleeve.FIXED_INCOME: RiskClass.FIXED_INCOME,
    IpsSleeve.COMMODITIES: RiskClass.COMMODITIES,
    IpsSleeve.FX: RiskClass.FX,
    IpsSleeve.ALTERNATIVES: RiskClass.ALTERNATIVES,
    IpsSleeve.CASH: RiskClass.CASH,
}

class OptimizerMappingError(ValueError):
    """Raised when a sleeve has no risk-class analog (no silent zero-μ)."""

def risk_class_for(sleeve: IpsSleeve) -> RiskClass:
    try:
        return _SLEEVE_TO_RISK[sleeve]
    except KeyError as err:                 # bubble to surface, never default
        raise OptimizerMappingError(
            f"no risk-class mapping for sleeve {sleeve!r}; cannot assign "
            "an expected return / covariance row"
        ) from err
```

The map is **total today** (all six members map), so po0 raises on no real fixture — the guard
exists to keep a *future* enum divergence loud. The position→sleeve leg of the three-enum chain is
already total-and-raising via `rollup_security_to_ips_sleeve` (handles `ETF` by ticker, raises
`ValueError` on an unsupported class), so po0 reuses `ips_sleeve_for_position` unchanged and does
not re-touch `security_master.AssetClass`.

### A.2 Build Σ once — `portfolio_covariance` does **not** return the matrix

`portfolio_covariance(states, assumptions)` returns `CovarianceResult(portfolio_variance,
portfolio_volatility, pct_variance_contributions, marginal_variance)` — **scalars and per-sleeve
contributions at a *given* weight vector**, not the Σ matrix. The QP gradient is
`∇f(w) = μ − λ·Σw`, which needs **Σ itself** at every iterate w, not the variance at w_current.
A careless po0 that calls `portfolio_covariance` inside the solver loop would (a) not get Σ at all
and (b) rebuild the `O(n²)` matrix every iteration. **Spec:**

```text
risk_classes = [ risk_class_for(s) for s in universe ]          # ordered, via §A.1 map
vol[i]       = assumptions.class_annual_vol[ risk_classes[i] ]
Σ[i][j]      = vol[i] · vol[j] · assumptions.pairwise_correlation(risk_classes[i], risk_classes[j])
μ[i]         = assumptions.class_expected_return[ risk_classes[i] ]
# Σ and μ are built ONCE, before the solve; this is the exact cov[i][j] formula in covariance.py.
```

`portfolio_covariance` is then called **once, at the final w\*** only, to report `RC_i =
pct_variance_contributions` — its real purpose here. (Reuse the formula, not the function, for the
solve; reuse the function, not the formula, for the report.)

**Solver (pure-Python, no external dependency):** projected-gradient ascent on
`f(w) = wᵀμ − (λ/2)wᵀΣw` with each iterate projected onto `{w : 1ᵀw = 1, w_min ≤ w ≤ w_max}` via the
**capped-simplex (Held–Wolfe / Michelot) projection** — a closed-form, exact, per-iteration
projection requiring no solver. Step size `1/L` with `L = λ·ρ(Σ)` (use a cheap Gershgorin/row-sum
bound for `ρ(Σ)`); stop when `‖w_{k+1} − w_k‖∞ < qp_tolerance` (pinned, e.g. `1e-8`) or
`qp_max_iters`. Solve in `float64`; quantize w\* back to `Decimal` and **re-assert `1ᵀw = 1` within
the `AssetPortfolio` validator's `0.0001` tolerance** before reporting — else the reporting-side
`AssetPortfolio` construction raises (a feature, not a bug: a w\* that fails the sum check is wrong).

### A.3 Feasibility, default bounds, illiquid sleeves

- **Feasibility guard (raises, no clip):** the box ∩ simplex is empty iff `Σ_s w_min[s] > 1` or
  `Σ_s w_max[s] < 1`. po0 checks this **before** the solve and raises
  `OptimizerInfeasibleError` with the offending sum — never silently clips to a wrong feasible point.
- **Sleeves with no `AllocationTarget`:** a sleeve present in positions but absent from
  `allocation_targets` defaults to `w_min = 0, w_max = 1` (free, not frozen) and is **named as a
  stated limitation** — the IPS expresses no policy for it, so the QP may move it; the report flags
  "no IPS bound" beside that sleeve rather than inventing one.
- **Illiquid (alternatives) sleeve:** included in **w** (so Σ and the budget `1ᵀw=1` are correct)
  but its `Δw` is **advisory-only and flagged** — po0 does not assume the alternatives leg is
  daily-tradable (research failure mode "illiquids treated as daily-rebalance assets"). Hard
  liquidity-laddering of illiquid Δw is deferred to po1.

### A.4 Spec deltas folded back into §3–§7

- §3 formula block is the **summary**; §A.1–A.3 is the **authoritative** po0 spec.
- §4 `RebalanceProposal` fields: `{target_weights, current_weights, delta_w, binding_bounds,
  unbounded_sleeves, risk_contributions, objective_value, lam, config_version}` — components always
  present; `binding_bounds`/`unbounded_sleeves` make the constraint set legible (PM axiom 6).
- §6 adds `test_sleeve_mapping_raises` (unmapped → `OptimizerMappingError`),
  `test_qp_infeasible_raises` (empty box∩simplex → `OptimizerInfeasibleError`), and
  `test_optimizer_mapping.py` as the **silent-success regression** for A.1.
- §7 adds `test_optimizer_qp.py::test_sigma_built_once` (solver does not call `portfolio_covariance`
  in the loop) and `::test_target_weights_sum_to_one` (Decimal quantization within `0.0001`).

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-06-28 | Initial draft (Claude). Plan-doc-only PR — no production code; suite unchanged. Grounded against shipped code: `run_tax_aware_optimizer` (TLH-only, IPS breach flags), `portfolio_covariance` (Σ scalars + `pct_variance_contributions`), `assumptions_for("base")` (μ/vol/ρ priors), `AllocationTarget` (`IpsSleeve` min/max/target), `_optimizer_propose` handler. po0 = constrained MV QP in sleeve-weight space, pure + advisory, behind the existing `optimizer.propose` op (no new op). **Addendum A** inverts the analyst's KeyError trap: `IpsSleeve` and `research.risk.AssetClass` are value-identical `StrEnum`s, so the naive μ-join *silently succeeds* — A.1 specifies an explicit raising `_SLEEVE_TO_RISK` map; A.2 catches that `portfolio_covariance` returns variance, not Σ, so the QP must build Σ once. Flagged the CLAUDE.md heuristics-table gap (Portfolio Optimization.md unlisted) for §10. |
