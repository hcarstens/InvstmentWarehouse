# Portfolio Optimization — Implementation Plan

**Status:** **po0 shipped**; **po1 turnover-budget half shipped** — hard
`‖Δw‖₁ ≤ τ` constraint behind `optimizer.propose` (ROUTE B convex step);
**po2 scenario-robust stress overlay shipped** — second solve under the
`high_risk` crisis Σ behind the same op (Option A; honesty #8 flipped). The
po1 **after-tax μ overlay** ("po1-tax") stays deferred, gated on the tax
estimate engine (tax leg pinned at $0; honesty #5 stays `not_computed`).
po3 (lot-discrete MIQP) remains doc-only.
**Date:** 2026-06-28
**Owner:** decision plane / `warehouse.decision.optimizer` (existing package — upgrade in place)
**Inputs:** [`research/portfolio_optimization.md`](research/portfolio_optimization.md) (DHA run, credence 0.70 — after-tax utility > unconstrained max-Sharpe; Σ regime-conditional; weight ≠ risk; μ estimation error dominates MV theory),
[`heuristics/Portfolio Optimization.md`](heuristics/Portfolio%20Optimization.md) (PO1–PO8),
[`heuristics/Mental Model of The Portfolio Manager.md`](heuristics/Mental%20Model%20of%20The%20Portfolio%20Manager.md) (axiom 6 — gate the binding-constraint count),
[`portfolio_analyst_implementation.md`](portfolio_analyst_implementation.md) (the structural template + the analyst signal that gives the optimizer its objective/constraint set; Addendum A.1 enum-join trap),
[`messaging_protocol.md`](messaging_protocol.md) (§5 catalog, S1 atomic-op rule — `optimizer.propose` already exists),
[`research/hnw_portfolios.md`](research/hnw_portfolios.md) (rung ladder, cohorts),
[`dev_contract_registry.md`](dev_contract_registry.md) (new `portfolio_optimization` track)

**Addenda:** §12 Addendum A (enum-join + Σ build spec); §13 Addendum B (pre-implementation review deltas — **authoritative for po0 fields/acceptance**).

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
| **Optimizer (v0, live)** | `decision.optimizer` → `optimizer.propose` | TLH **`TradeProposal`** sells + IPS min/max breach flags on class weights | EVALUATE |
| **Optimizer (v1, this plan)** | `decision.optimizer` → `optimizer.propose` (**same op**) | **Constrained MV QP** → additive `rebalance` (w\*/Δw/RC); v0 TLH **unchanged** | EVALUATE |

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
| 5 | After-tax effective μ (TLH / asset-location / gain-deferral) | `TaxEstimator` seam; default `ZeroTaxEstimator` → tax leg `$0` (identity overlay) | **`not_computed`** under the $0 seam; **flips → computed at the Quantile estimator stage** (§14 Addendum C) |
| 6 | Turnover `‖Δw‖₁` / budget `τ` | `RebalanceProposal.turnover_l1` (po0) **+ hard `‖Δw‖₁ ≤ τ` cap from `turnover_budget_pct`** (po1, ROUTE B) | **reported po0 → constrained po1 (within budget)** ✓ (§B.3) |
| 7 | Lot-discrete sell/hold binaries `x_l` + wash-sale graph | MIQP, no external solver allowed | **`not_computed`** (deferred po3) |
| 8 | Regime-conditional / scenario-robust Σ | second solve under the `high_risk` crisis Σ; base-MV w\* vs stress-robust w\* + regime gap `‖w*_base − w*_stress‖₁` (§B.8 Option A) | **po2 — computed** ✓ |
| 9 | Factor-model Σ (n > 50 sleeves) | class-block Σ only (6 sleeves) | **`not_computed`** (out of scope) |
| 10 | OOS validation of μ/Σ | no signal/screen pipeline (shared gap w/ analyst checkpoint 4) | **`not_computed`** |
| 11 | Risk-free blend / CML leverage (PO3), Kelly sizing (PO4) | no cash-leverage or edge-estimate layer | **`not_computed`** (out of scope) |

**Stated limitations (surfaced in the report + dashboard, not hidden):**

- **μ is an ex-ante assumption** (`CLASS_EXPECTED_RETURN`), not a forecast — PO6: optimizers
  amplify input error and overweight high-μ sleeves that are often noise. po0's defense is the
  **box constraints `w_min ≤ w ≤ w_max` as diversification floors/caps** (PO6 last sentence), not
  μ-shrinkage; shrinkage toward an equilibrium prior is deferred and labelled as such.
- **Base regime + crisis regime** (PO7 non-stationarity): correlations spike toward 1 in crises and
  the diversification benefit collapses exactly when needed. po0/po1 optimized on the normal-regime
  prior and **said so**; **po2 now ships the scenario-robust overlay** — a second solve under the
  `high_risk` crisis Σ, reporting base-MV w\* vs stress-robust w\* and the regime gap
  `‖w*_base − w*_stress‖₁` (§B.8 Option A). Honest caveat: `high_risk` crisis-blends ρ **and** scales
  vols ×1.4 — a crisis *regime*, not a correlation-only shock; the panel + docs say so.
- **Weight ≠ risk** (research §"Multi-Asset Specifics" #2): equal sleeve weights carry unequal
  `RC_i`. po0 therefore reports `RC_i` next to w\*, so the advisor reads risk space, not just
  weight space.
- **Illiquids sit outside daily Δw** (research #5): alternatives are a sleeve in **w** but cannot
  be traded daily. po0's Δw on the alternatives sleeve is **advisory-only and flagged** via
  `illiquid_advisory_sleeves` (§B.5); po0 does not assume it is executable (failure mode
  "illiquids treated as daily-rebalance assets").
- **Sleeve-native sensitivity units** (research #3: beta, DV01, greeks): class-block Σ aggregates
  approximately; po0 does not bridge to a unified dollar-greek stack — **`not_computed`** (§B.7).
- **Alternative objectives** (tracking error, ERC): out of scope for po0–po2; constrained MV only
  (§B.7). Policy drift vs IPS target is **reported** on `RebalanceProposal`, not optimized (§B.4).

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
| Additive `OptimizationResult.rebalance: RebalanceProposal \| None` | Upgrade **behind** `optimizer.propose`; fields per §B.2; **no new op** (S1) |
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

### po0 — constrained mean-variance QP *(shipped)*

**Goal:** `optimizer.propose` returns a target sleeve-weight vector + Δw + risk contributions, on
real Σ inside IPS bounds; PM carries it. Rebalance is advisory — **no trades from the QP path**
(v0 TLH `trades` unchanged; §B.1).

| Task | File(s) |
| --- | --- |
| `RebalanceProposal` (frozen): canonical field set §B.2 | `decision/optimizer/models.py` *(new)* |
| `solve_qp(mu, sigma, w_min, w_max, *, lam, tol, max_iters)` — projected-gradient + capped-simplex projection; feasibility guard raises | `decision/optimizer/qp.py` *(new)* |
| `run_mv_rebalance(...)`: assemble universe, `_SLEEVE_TO_RISK` (raises on unmapped, §A.1), build Σ once (§A.2), solve, roll up `RC_i` via `portfolio_covariance` at w\* | `decision/optimizer/rebalance.py` *(new)* |
| Additive `OptimizationResult.rebalance`; `_optimizer_propose` calls `run_mv_rebalance` and **constructs** the result with it (or `model_copy(update=...)` — frozen forbids post-hoc set; §B.1) | `decision/optimizer/__init__.py`, `messaging/handlers.py` |
| `optimizer_config_version`, `risk_aversion_lambda`, `qp_tolerance`, `qp_max_iters` | `config.py` |
| Freeze + register `RebalanceProposal` **and** `OptimizationResult` | `integrity/frozen_registry.py`, `tests/test_frozen.py` |
| Rebalance panel (target-vs-current w, Δw, policy drift, binding bounds, `RC_i`, illiquid flags,
  μ source label) + loader | `dashboard/optimizer_data.py` *(new)*, `dashboard/render_phase3.py`,
  `dashboard/phases.py` |

**Acceptance:** §B.9 (includes items below).

- **Zero-Δ probe** (PASS falsifier): a household already at the unconstrained interior optimum →
  `‖Δw‖∞ ≈ 0`, `binding_bounds == []` (current == optimum; §9).
- A household breaching a sleeve max → w\* clips to `w_max`, that bound appears in `binding_bounds`,
  Δw moves **toward** feasibility (mirrors `test_concentrated_stress_optimizer_documents_binding`).
- **Monotone in λ:** raising `risk_aversion_lambda` lowers `wᵀΣw` at w\* (more risk-averse → lower
  portfolio variance) — a property test, no magic numbers.
- **Unmapped sleeve raises** `OptimizerMappingError` — never a silent zero-μ (§A.1).
- **Infeasible bounds raise** (`Σ w_min > 1` or `Σ w_max < 1`) — never a silent clip.
- `result.rebalance is not None`; **no `TradeProposal` from the rebalance path**; v0 TLH trades
  coexist (`test_rebalance_coexists_with_tlh_trades`; §B.1).
- `test_pm_no_new_ops` still green (`pm.* == {pm.advise}`; `optimizer.*` unchanged).
- `pytest tests/test_frozen.py` green (`OptimizationResult`, `RebalanceProposal` immutable).

### po1 — turnover budget *(turnover half shipped)* + after-tax (TLH) overlay *(deferred "po1-tax")*

**Goal:** constrain `‖Δw‖₁ ≤ τ` (PO8) and run the TLH/asset-location overlay **inside** IPS bounds.

| Task | File(s) | Status |
| --- | --- | --- |
| L1 turnover constraint from `ips.turnover_budget_pct`; rebalance on threshold drift, not calendar (PO8) | `decision/optimizer/rebalance.py` | **shipped** (ROUTE B) |
| After-tax effective μ (TLH harvest value, gain deferral) — overlay, not substitute | `decision/optimizer/rebalance.py`, `decision/tax/estimator.py` | **seam shipped at $0; estimates deferred** — `TaxEstimator` wired with `ZeroTaxEstimator` (identity, #5 stays `not_computed`); `QuantileTaxEstimator` → `LLMTaxEstimator` deferred (§14 Addendum C) |
| Optional μ tilt from analyst `active_return` / NPA (advisory weight, **not** a hard constraint) | `decision/optimizer/rebalance.py` | **deferred** — open-Q#13 v0; not half-wired |

**Turnover half (shipped) — ROUTE A vs B decision.** Adding `‖w − w_current‖₁ ≤ τ`
makes the feasible set box ∩ simplex ∩ L1-ball. Two routes:

- **(A) RIGOROUS** — projected-gradient with Dykstra alternating projection between the
  capped-simplex/box projection and the L1-ball projection (Duchi et al. 2008). The true
  L1-constrained MV optimum; heavier.
- **(B) FIRST-CUT HEURISTIC (shipped)** — solve the po0 turnover-unconstrained w\*; if
  `‖w*−w_current‖₁ > τ`, take the budget-scaled convex step
  `w_budget = w_current + (τ/‖Δw‖₁)·(w* − w_current)`. A feasible-DIRECTION step toward the MV
  optimum (exact on the budget, `‖Δw‖₁ = τ`), **not** the L1-constrained argmax — the constrained
  optimum may lie off the segment. ROUTE A is the documented upgrade.

**Why B:** it matches the project's "pragmatic staged, documented upgrade path" ethos, is exact on
the budget, and on a box-feasible `w_current` preserves every po0 invariant (Σw=1, box) cheaply.
**Limitation (honest):** when `w_current` itself **breaches** the IPS box, `w_budget` is projected
back onto box ∩ simplex (`project_capped_simplex`) to keep `Σw=1`/feasibility, and turnover can then
drift slightly off `τ` (it is no longer a pure convex step) — see the demo fixture below.

**τ convention (honest).** `‖Δw‖₁` is **two-way** turnover (`Σ|Δw| = buys + sells`, since
`ΣΔw = 0`); one-way `= ‖Δw‖₁/2`. `turnover_budget_pct` is documented as **annual** in the IPS, but a
rebalance is one event — po1 treats it as the **per-rebalance** `‖Δw‖₁` cap and says so (labelled
limitation; no silent horizon reconciliation).

**Demo-budget pin.** The §9 cohort IPS leaves `turnover_budget_pct` unset, so the dashboard loader
injects a **demo-only** `optimizer_demo_turnover_budget_pct` (`model_copy` on the IPS), labelled
"demo" on the panel, so the live state shows "within budget"/"capped at budget".

**Acceptance (turnover half):** Δw respects `‖Δw‖₁ ≤ τ` (within quantization tol) on a slack-bound
fixture where `‖Δw*‖₁ > τ`; `turnover_budget_pct is None` is a **no-op** (w\* and every po0 field
byte-identical); a slack budget (`‖Δw*‖₁ < τ`) leaves w\* unchanged with `turnover_binding=False`.
Falsifiers: `tests/test_optimizer_turnover.py` (`test_turnover_budget_binds`,
`test_budget_step_is_convex_and_exact`, `test_turnover_budget_none_is_noop`,
`test_turnover_budget_slack_unbinding`, `test_turnover_advisory_no_trade`,
`test_turnover_no_new_ops`) + `test_optimizer_panel_shows_turnover_budget_state`.

**Acceptance (po1-tax, deferred):** flip honesty #5 (after-tax μ) from `not_computed` to computed
**only** when the tax leg is live; analyst tilt changes w\* but never forces a bound. **Not shipped
this window** — gated on the tax estimate engine.

### po2 — scenario-robust stress overlay *(shipped)*

**Goal:** complement base-regime MV with a crisis-regime re-solve (PO7).

**Shipped Option A (§B.8 RECOMMENDED):** a SECOND constrained MV QP under the `high_risk`
crisis-correlation Σ, reported beside the base solve with the regime gap
`‖w*_base − w*_stress‖₁`. It reuses `solve_qp` / the Σ-build / the turnover treatment **verbatim**
on an alternate Σ (the overlay re-enters `run_mv_rebalance` with the crisis priors and
`compute_stress=False` to break the recursion), is the lightest route, and flips honesty #8 cleanly.
Option C (scenario P&L via `evaluate_stress` over the `STRESS_SCENARIOS` return-shock packs) is the
documented richer upgrade; Option B (a single objective with a `max_s w'Σ_s w` penalty) the
alternative single-objective form.

| Task | File(s) | Status |
| --- | --- | --- |
| Crisis-regime re-solve + regime gap + stress RC/objective (Option A) | `decision/optimizer/robust.py` *(new)* | **shipped** |
| Additive frozen `RebalanceProposal` fields (`stress_regime`, `stress_target_weights`, `stress_delta_w`, `regime_gap_l1`, `stress_objective_value`, `stress_risk_contributions`) | `decision/optimizer/models.py` | **shipped** |
| `optimizer_stress_regime` pin (`high_risk`) | `config.py` | **shipped** |
| Panel: base-vs-stress w\* side by side + regime-gap line (material badge) | `dashboard/optimizer_data.py`, `dashboard/render_phase3.py` | **shipped** |

**Acceptance (met):** honesty-matrix #8 flipped `not_computed` → computed; on a SLACK-bound synthetic
fixture (wide bounds, base LOW ρ vs crisis HIGH ρ) stress-robust w\* differs from base-MV w\* with
`regime_gap_l1 > 0` (PO7 — diversification collapses under crisis ρ), both Σw=1 + box-feasible; the
`concentrated_stress` rung-4 seed-42 fixture produces both solves with the gap reported. Base path
byte-identical to po1 (overlay additive). #5 (after-tax μ) stays `not_computed` (tax seam $0).
Falsifiers: `tests/test_optimizer_robust.py` (`test_stress_w_star_differs_from_base`,
`test_concentrated_fixture_regime_gap`, `test_base_path_byte_identical_to_po1`,
`test_robust_advisory_no_trade`, `test_after_tax_mu_still_not_computed`, `test_robust_no_new_ops`) +
`test_optimizer_panel_shows_base_vs_stress`.

**Honest limitation:** bound-determined fixtures (tight IPS boxes) pin both optima to the same
bounds → regime gap ~0; the binding "stress ≠ base" acceptance therefore runs on a slack-bound
synthetic fixture (mirrors po0/po1's solve-level property tests). `high_risk` scales vols ×1.4 as
well as ρ — a crisis regime, not correlation-only.

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
| μ never labelled "forecast"/"alpha" — **test scans rendered copy**, not just the `mu_source` Literal (trivially safe by typing) | PO6 + analyst A.3 | `test_mu_not_named_forecast` |
| `risk_aversion_lambda` + QP tolerances **pinned** to `optimizer_config_version` | audit replay | `test_optimizer_config_pinned` |
| Binding-constraint set stays **legible/few** (PM axiom 6) | PM mental model 6 | `test_binding_bounds_legible` |
| Illiquid sleeves flagged in `illiquid_advisory_sleeves` (sleeve-level, not magnitude-gated) | research #5, PM Addendum C | `test_illiquid_sleeve_flagged` (§B.5) |
| v0 TLH `trades` unchanged; rebalance path emits no trades | §B.1 | `test_rebalance_coexists_with_tlh_trades` |
| μ labelled **ex-ante class assumption** on dashboard | PO6 + §B.9 | `test_mu_source_label_on_panel` |
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
| `tests/test_optimizer_rebalance.py` | universe union, `_SLEEVE_TO_RISK` raise, Σ built once, `RC_i` rollup, advisory (no trade staged), TLH coexistence, illiquid flags, `turnover_l1` + `policy_drift` |
| `tests/test_optimizer_mapping.py` | explicit sleeve→risk map total + raises; **regression for the silent-success trap** (§A.1) |
| `tests/test_pm_workflow.py` | *(extend)* `AdviceBundle.proposal.rebalance` present on demo + HNW rung 3 |
| `tests/test_synthetic_ips_workflow.py` | *(extend)* concentrated_stress binding bounds via QP (alongside the existing v0 assertion) |
| `tests/test_dashboard.py` | *(extend)* rebalance panel: target-vs-current w, Δw, binding bounds, `RC_i` |
| `tests/test_frozen.py` | `OptimizationResult`, `RebalanceProposal` immutable (+ falsifier) |

**CI gate:** QP correctness (zero-Δ + binding + monotone) + mapping raises + advisory no-persist +
config pinned + PM op-surface unchanged + §B.9 acceptance (turnover, policy drift, illiquid flags,
TLH coexistence, μ source label).

---

## 8. Dependencies & build order

```text
risk Σ/μ (portfolio_covariance, assumptions_for) + IPS allocation_targets + analyst pa0–pa2   [shipped]
  └─ po0 (constrained MV QP; advisory w*/Δw/RC behind optimizer.propose)        [shipped]
       └─ po1 (turnover ‖Δw‖₁≤τ shipped; after-tax TLH overlay $0 seam)         [turnover shipped]
            └─ po2 (scenario-robust stress overlay — PO7, Option A)             [shipped]
                 └─ po3 (lot-discrete MIQP — documented upgrade path)            [deferred — doc only]

Held on purpose (non-blocking):
  TaxEstimator seam ($0 default)  →  unblocks po2 + execution + reporting + end-to-end stress
       └─ QuantileTaxEstimator    →  flips after-tax μ (#5) not_computed → computed (po1-tax)
            └─ LLMTaxEstimator    →  judgment edge cases (QSBS, trust DNI, AMT) — last
  (staged ladder — §14 Addendum C; $0 completes the overlay STRUCTURE, not its behavior)
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
| Freezing `OptimizationResult` breaks an existing mutator, **and blocks `_optimizer_propose` from setting `.rebalance` post-hoc** | po0 audits `runner.py` / `compare.py` mutation sites before flipping `frozen=True`; the handler **constructs** the result with `rebalance=` or `model_copy(update=...)`, never assigns (§B.1); `test_frozen.py` falsifier proves immutability |
| Decimal↔float boundary in the solver | Solve in `float64`; **clip float dust into `[w_min, w_max]`** (avoids `AllocationSlot.weight ge=0/le=1` raises), quantize to `Decimal`, then **explicitly re-assert `Σw=1` within 0.0001 in po0** — the `AssetPortfolio` sum validator is *not* in po0's path (it builds `SleeveRiskState`/`AllocationSlot` directly) (§A.2) |
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
`f(w) = wᵀμ − (λ/2)wᵀΣw` with each iterate projected onto `{w : 1ᵀw = 1, w_min ≤ w ≤ w_max}` via a
**capped-simplex / continuous quadratic-knapsack projection** (the bounded-box generalization of
the unit-simplex projection — Held–Wolfe–Crowder / Pardalos–Kovoor; Michelot 1986 covers only the
`w ≥ 0` unit-simplex case) — a closed-form, exact, per-iteration projection requiring no solver.
Step size `1/L` with `L = λ·ρ(Σ)` (use a cheap Gershgorin/row-sum bound for `ρ(Σ)`); stop when
`‖w_{k+1} − w_k‖∞ < qp_tolerance` (pinned, e.g. `1e-8`) or `qp_max_iters`. Solve in `float64`, then:

1. **Clip float dust into the box** before anything else — a `−1e-12` weight raises on
   `AllocationSlot.weight`'s `ge=0` (and `> 1` on `le=1`); clamp to `[w_min, w_max]` within
   `qp_tolerance`.
2. Quantize w\* to `Decimal`.
3. **Explicitly re-assert `Σ_s w*[s] = 1` within `0.0001`** in po0 — this is an *own* guard, not a
   free side-effect: po0 reports `RC_i` by building `SleeveRiskState`/`AllocationSlot` directly and
   calling `portfolio_covariance`; it never constructs an `AssetPortfolio`, so that model's sum=1
   validator is **not** in the path. A w\* that fails the sum check raises `OptimizerInfeasibleError`
   (a feature, not a bug — it means the projection or quantization is wrong).

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
- §4 `RebalanceProposal` fields: **canonical set in §B.2** (supersedes the partial list here).
- §6 adds `test_sleeve_mapping_raises` (unmapped → `OptimizerMappingError`),
  `test_qp_infeasible_raises` (empty box∩simplex → `OptimizerInfeasibleError`), and
  `test_optimizer_mapping.py` as the **silent-success regression** for A.1.
- §7 adds `test_optimizer_qp.py::test_sigma_built_once` (solver does not call `portfolio_covariance`
  in the loop) and `::test_target_weights_sum_to_one` (Decimal quantization within `0.0001`).

---

## 13. Addendum B — Pre-implementation edits (review deltas, po0 spec)

Review against [`research/portfolio_optimization.md`](research/portfolio_optimization.md) and
[`heuristics/Portfolio Optimization.md`](heuristics/Portfolio%20Optimization.md) (PO1–PO8).
**Authoritative for po0** where it extends Addendum A. Fold into code on the po0 PR.

### B.1 v0 TLH trades vs po0 advisory rebalance — two fields, one op

Live v0 (`run_tax_aware_optimizer`) **emits `TradeProposal` sells** for TLH harvests and records
IPS min/max breaches in `binding_constraints` — it is not flags-only. po0 adds a **second output
leg** on the same op:

| Field | Source | po0 behavior |
| --- | --- | --- |
| `OptimizationResult.trades` | v0 TLH heuristic | **Unchanged** — lot-level harvest proposals |
| `OptimizationResult.rebalance` | po0 `run_mv_rebalance` | **New** — sleeve-weight w\*/Δw/RC; **no trades** |

**Invariant:** the QP/rebalance path never appends to `trades`. `_optimizer_propose` calls both
engines and **constructs one `OptimizationResult` carrying both fields** — because po0 freezes
`OptimizationResult` (§4), `result.rebalance` **cannot be set after construction**. Either thread
`rebalance=` into the `run_tax_aware_optimizer` return (preferred — single construction site) or
`result.model_copy(update={"rebalance": proposal})` in the handler (the CLAUDE.md model-copy
pattern). Do not write `result.rebalance = ...`; the frozen model will raise. PM axiom 7 and the
human gate treat rebalance as advisory; TLH trades remain a separate approval surface (unchanged).

**Test:** `test_rebalance_coexists_with_tlh_trades` — demo household with loss lots →
`len(result.trades) > 0` **and** `result.rebalance is not None`; rebalance path alone never
creates trades.

### B.2 Canonical `RebalanceProposal` fields (supersedes §4 / A.4 partial lists)

Single field list for po0 — all components always present (empty collections / `None` where noted):

| Field | Type | Role |
| --- | --- | --- |
| `target_weights` | `dict[IpsSleeve, Decimal]` | MV optimum w\* |
| `current_weights` | `dict[IpsSleeve, Decimal]` | As-of sleeve weights |
| `delta_w` | `dict[IpsSleeve, Decimal]` | w\* − w_current (MV rebalance vector) |
| `policy_drift` | `dict[IpsSleeve, Decimal]` | w_current − IPS `target_weight` (0 if no target; §B.4) |
| `binding_bounds` | `list[str]` | IPS bounds active at w\* (legible set — PM axiom 6) |
| `unbounded_sleeves` | `list[IpsSleeve]` | Sleeves in positions with no `AllocationTarget` (A.3) |
| `illiquid_advisory_sleeves` | `list[IpsSleeve]` | Δw flagged non-executable (§B.5); po0 = `{ALTERNATIVES}` |
| `risk_contributions` | `dict[IpsSleeve, Decimal]` | `RC_i` at w\* (pct variance share) |
| `turnover_l1` | `Decimal` | `‖Δw‖₁` — reported po0, constrained po1 (§B.3) |
| `objective_value` | `Decimal` | `w*ᵀμ − (λ/2)w*ᵀΣw` at solve |
| `mu_source` | `Literal["ex_ante_class_assumption"]` | PO6 honesty label — single-value by typing; the real guard is on **rendered copy** (§B.9) |
| `lam` | `Decimal` | `risk_aversion_lambda` used in solve |
| `config_version` | `str` | `optimizer_config_version` pin |

Freeze + register per §4. The dashboard and PM **axiom enrichment**
(`portfolio_manager_implementation.md` Addendum C) read these fields directly.

### B.3 Turnover `‖Δw‖₁` — report po0, constrain po1

Honesty matrix #6: po0 **computes and reports** `turnover_l1 = Σ_s |Δw[s]|` on every
`RebalanceProposal`. When `ips.turnover_budget_pct` is set, po0 also reports
`turnover_budget_pct` alongside (informational — no constraint yet). po1 adds the hard constraint
`‖Δw‖₁ ≤ τ` to the QP/projection and flips dashboard status from "reported" to "within budget".

PO8 rebalance-on-drift (not calendar) stays on PM axiom 7 / po1 — po0 runs whenever
`optimizer.propose` is called; it does not implement a drift trigger.

### B.4 Policy drift vs MV Δw — reported, not optimized

Research defines drift `d = w_current − w_policy`; the QP optimizes `Δw = w* − w_current`.
IPS `target_weight` is **not** a QP objective term in po0 (no tracking-error objective — §B.7).

**Spec:** for each sleeve with an `AllocationTarget`, set
`policy_drift[s] = w_current[s] − target.target_weight`; sleeves without a target → `Decimal("0")`.
Report on `RebalanceProposal` and the rebalance panel. Hard min/max breach detection stays on
`policy.check` / `drift_vs_ips()`; the optimizer does not duplicate breach alerts — it surfaces
**where the MV optimum sits relative to policy center**, not whether policy is violated.

### B.5 Illiquid sleeve flags — field name pinned for PM axiom 6

Research failure mode: illiquids treated as daily-rebalance assets. po0 includes alternatives in
**w** (correct Σ and `1ᵀw=1`) but marks non-executable Δw explicitly:

- Field: **`illiquid_advisory_sleeves: list[IpsSleeve]`**
- po0 rule: if `IpsSleeve.ALTERNATIVES ∈ universe`, append `ALTERNATIVES` to the list —
  **membership is sleeve-level, not magnitude-gated**. The flag fires even when `delta_w` is
  near zero (e.g. the §9 zero-Δ probe), so the dashboard always shows the non-executable
  constraint. (Do **not** gate on `|delta_w| > qp_tolerance` — that would drop the badge exactly
  when the sleeve is correctly left untouched, and would contradict `test_illiquid_sleeve_flagged`.)
- Dashboard: render an **"advisory only — not daily tradable"** badge beside those sleeves' Δw rows.
- PM axiom enrichment (Addendum C), axiom 6: count `illiquid_advisory_sleeves` toward the legible
  binding/feasibility set.

Hard liquidity-laddering (committed-capital caps on alternatives Δw) remains po1.

### B.6 λ calibration — platform prior, not household-specific

`risk_aversion_lambda` is pinned to `optimizer_config_version` as a **platform prior** — not
calibrated per household from IPS risk tolerance or `risk.evaluate` output. po0 finds **one**
efficient-frontier point (fixed λ), not a frontier trace (PO2 partial satisfaction: dominance is
shown via Δw magnitude and binding bounds, not an explicit "current w is dominated" flag).

Household-specific λ / frontier tracing is out of scope until a future slice justifies it here.

### B.7 Out-of-scope objectives and model limits (named, not silent)

| Topic | po0 stance |
| --- | --- |
| Tracking-error objective `(w − w_policy)'Σ(w − w_policy)` | Out of scope — policy drift **reported** only (B.4) |
| Equal risk contribution (ERC) / risk-budget rebalance | Out of scope — `RC_i` **reported** at w\* for advisor review |
| Native sensitivity units (beta, DV01, greeks) | **`not_computed`** — class-block Σ only; no unified greek stack |
| PO3 CML / cash-leverage blend, PO4 Kelly sizing | Out of scope (honesty matrix #11) |

### B.8 po2 robust objective — **SHIPPED Option A**

po2 complements base-regime MV with crisis stress (PO7 — correlations spike toward 1 in a crisis
and the diversification benefit collapses exactly when needed). **Shipped Option A**: a second
constrained MV QP under the `high_risk` crisis-correlation Σ, reporting base-MV w\* vs stress-robust
w\* + the regime gap `‖w*_base − w*_stress‖₁`. Chosen because it reuses `solve_qp`/the Σ-build
verbatim (lightest), drops straight into `run_mv_rebalance(..., assumptions=...)`, and flips
honesty #8 cleanly. Option C (scenario P&L) named as the documented richer upgrade; Option B as the
single-objective alternative.

**Grounding — two distinct stress representations already ship; do not conflate them:**

| Object | What it is | Where | Use |
| --- | --- | --- | --- |
| **Crisis-correlation Σ** = the `high_risk` **regime** | A full `RiskAssumptions` — ρ → ρ + (`CRISIS_CORRELATION` 0.85 − ρ)·(`CRISIS_BLEND` 0.80), vols ×1.4 (`HIGH_VOL_MULTIPLIER`), PSD-validated on register | `research/risk/scenarios.py` (`assumptions_for("high_risk")`, `scenario_names()`) | **Option A** — drops straight into `run_mv_rebalance(..., assumptions=...)` / the Σ-build |
| **Return-shock packs** `2008_liquidity` / `2020_pandemic` / `2022_inflation` | Per-class % **return shocks**, NOT correlation matrices | `STRESS_SCENARIOS` in `research/risk/assumptions.py`, applied as P&L by `evaluate_stress(slots, assumptions)` in `research/risk/stress.py` | **Option C** — scenario P&L simulation |

| Option | Form | Notes |
| --- | --- | --- |
| **A (default candidate, RECOMMENDED)** | Re-solve the constrained MV QP a second time under the **`high_risk` crisis-correlation Σ**; report base-MV w\* vs stress-robust w\* side by side + the regime gap `‖w*_base − w*_stress‖₁` | Reuses `solve_qp`/the Σ-build **verbatim** (PO7 via alternate ρ); lightest; flips honesty #8 cleanly |
| **B** | Base solve + penalty `max_s (w'Σ_s w)` over crisis regime(s) | Single objective; needs a penalty-weight pin in `config.py` |
| **C** | Scenario P&L simulation primary (research preference) — evaluate base vs robust w\* under the `STRESS_SCENARIOS` return-shock packs via `evaluate_stress` | Heavier; uses the risk-plane P&L hook; name as the documented richer upgrade behind A |

**Honest caveat for A:** `high_risk` scales vols ×1.4 **and** crisis-blends ρ — it is a crisis
*regime*, not a correlation-only shock. If a pure correlation-shock demonstration is wanted,
register a correlation-only regime in `scenarios.py` and label it; otherwise reuse `high_risk` and
say so in the panel + docs. Do not imply "correlation-only".

The po0/po1 dashboard label "base-regime Σ only" has been **replaced** with a live base-vs-stress
comparison + regime-gap line now that po2 has shipped and honesty matrix #8 is flipped.

### B.9 po0 acceptance additions (from review)

Add to po0 acceptance (§5) and CI gate (§7):

| Criterion | Test |
| --- | --- |
| `turnover_l1` present and equals `Σ|Δw|` | `test_rebalance_turnover_l1` |
| `policy_drift[s] = w_current[s] − target_weight[s]` | `test_policy_drift_reported` |
| `illiquid_advisory_sleeves` contains `ALTERNATIVES` when in universe | `test_illiquid_sleeve_flagged` |
| v0 TLH trades + rebalance both populated when applicable | `test_rebalance_coexists_with_tlh_trades` |
| Dashboard shows μ source label (`mu_source`) | `test_mu_source_label_on_panel` |
| **Rendered panel + rationale copy** never contains "forecast"/"alpha" for μ (scans text, not just the `mu_source` Literal — which is trivially safe by typing; mirrors analyst `test_residual_not_named_alpha`) | `test_mu_not_named_forecast` |

### B.10 Spec deltas folded back

- §1 v0 row: TLH `TradeProposal` + breach flags (not flags-only).
- §2 honesty #6: `turnover_l1` reported po0; constrained po1.
- §2 stated limitations: native units + alternative objectives + policy drift reporting.
- §4–§7: canonical fields (B.2), acceptance (B.9), invariants, test plan updated.
- A.4 field list: defers to B.2.

---

## 14. Addendum C — tax estimator seam & staged estimates (po1-tax)

The po1-tax overlay (after-tax effective μ) is gated on a tax engine that does
not exist. Rather than block the whole downstream pipeline (po2 stress,
execution, reporting, end-to-end stress testing) on it, po1-tax splits into a
**seam now** + **estimates later**, against a swappable `TaxEstimator` whose
default returns `$0`. **Authoritative for the po1-tax seam.**

### C.1 Why $0 unblocks the pipeline but not the overlay's behavior

Pinning tax at `$0` (the existing `evaluate_tax_scenario` stub) lets every
**non-tax** slice build and stress-test end-to-end. But with tax `$0`
everywhere the after-tax overlay is an **identity**: after-tax μ ≡ pre-tax μ,
and TLH-harvest / gain-deferral / asset-location value are all `0`. So `$0`
completes the overlay's **structure**, not its **behavior**.

**Honesty rule (do not fake — §2):** honesty matrix #5 stays `not_computed`
under the `$0` seam. A trivially-zero overlay claiming "after-tax" *is* the
"pre-tax MV on an after-tax mandate" failure mode. #5 flips to `computed` only
at the Quantile stage, when the estimator returns a non-trivial drag and the
overlay actually moves w\*.

### C.2 The staged estimator ladder

| Stage | Estimator | After-tax μ | honesty #5 | When |
| --- | --- | --- | --- | --- |
| seam | `ZeroTaxEstimator` (default) | ≡ pre-tax μ (identity) | `not_computed` | **now** — unblocks po2 + stress |
| estimate v0 | `QuantileTaxEstimator` | best-guess drag by holding period / class / lot gain | **flips → computed** | mid |
| estimate v1 | `LLMTaxEstimator` | judgment edge cases (QSBS, trust DNI, AMT interplay) | computed (refined) | last |

Same "pragmatic staged, documented upgrade path" ethos as ROUTE B → ROUTE A for
turnover (§5 po1).

### C.3 Seam granularity — decide now, even at $0

The existing `tax.scenario` / `evaluate_tax_scenario` returns **portfolio-level**
baseline/scenario/delta. The optimizer overlay needs **per-sleeve** (or per-lot
for TLH harvest value) tax drag on μ — finer-grained. Define the `TaxEstimator`
interface at that granularity **now** (returning `$0`) so the seam is not
reshaped when `QuantileTaxEstimator` lands.

```python
# decision/tax/estimator.py
class TaxEstimator(Protocol):
    def sleeve_mu_drag(
        self, universe: list[IpsSleeve], *, settings: Settings | None = None
    ) -> dict[IpsSleeve, Decimal]:
        """After-tax μ adjustment per sleeve (subtracted from ex-ante μ)."""

class ZeroTaxEstimator:
    is_zero = True            # identity overlay marker — keeps #5 not_computed
    def sleeve_mu_drag(self, universe, *, settings=None):
        return {s: Decimal("0") for s in universe}
```

`run_mv_rebalance` takes `tax_estimator: TaxEstimator | None = None`
(default `ZeroTaxEstimator`); the overlay computes `μ_after_tax[s] = μ[s] −
drag[s]` **before** the solve, inside the existing IPS box (overlay, not
substitute). When the estimator `is_zero`, the overlay is skipped entirely so
w\* is byte-identical to the pre-overlay path.

### C.4 Acceptance (seam, now)

| Criterion | Test |
| --- | --- |
| `ZeroTaxEstimator` overlay is a strict **no-op** — w\*, Δw, every po1 field byte-identical to the no-overlay path | `test_zero_tax_estimator_is_noop` |
| honesty #5 **stays `not_computed`** (label asserted, not faked) | `test_after_tax_mu_not_computed_under_zero` |
| Seam **carries** a drag — injecting a non-zero stub estimator moves w\* (proves the wiring without shipping real numbers) | `test_tax_estimator_drag_moves_w_star` |
| μ never labelled "forecast"/"alpha" (overlay copy) | existing scan |

The non-zero-stub test is the key falsifier: it proves the seam transmits a tax
drag **without** committing to any tax magnitude — the Quantile/LLM estimators
drop in later behind the same interface.

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-06-28 | Initial draft (Claude). Plan-doc-only PR — no production code; suite unchanged. Grounded against shipped code: `run_tax_aware_optimizer` (TLH-only, IPS breach flags), `portfolio_covariance` (Σ scalars + `pct_variance_contributions`), `assumptions_for("base")` (μ/vol/ρ priors), `AllocationTarget` (`IpsSleeve` min/max/target), `_optimizer_propose` handler. po0 = constrained MV QP in sleeve-weight space, pure + advisory, behind the existing `optimizer.propose` op (no new op). **Addendum A** inverts the analyst's KeyError trap: `IpsSleeve` and `research.risk.AssetClass` are value-identical `StrEnum`s, so the naive μ-join *silently succeeds* — A.1 specifies an explicit raising `_SLEEVE_TO_RISK` map; A.2 catches that `portfolio_covariance` returns variance, not Σ, so the QP must build Σ once. Flagged the CLAUDE.md heuristics-table gap (Portfolio Optimization.md unlisted) for §10. |
| 2026-06-28 | **Addendum B** — pre-implementation review deltas: v0 TLH trades vs po0 advisory rebalance split (B.1); canonical `RebalanceProposal` fields (B.2); turnover report po0 / constrain po1 (B.3); policy drift reported not optimized (B.4); `illiquid_advisory_sleeves` pinned for PM axiom 6 (B.5); λ as platform prior (B.6); named out-of-scope objectives (B.7); po2 robust objective options pinned for po2 kickoff (B.8); po0 acceptance tests (B.9). §1–§7 cross-refs updated. |
| 2026-06-28 | **po0 shipped (Claude).** Constrained mean-variance QP landed behind the existing `optimizer.propose` op — **no new atomic op** (`test_pm_no_new_ops` green). New `decision/optimizer/models.py` (`RebalanceProposal` frozen + canonical §B.2 fields, `OptimizerMappingError`/`OptimizerInfeasibleError`), `qp.py` (pure-Python projected-gradient ascent + capped-simplex/quadratic-knapsack projection, Gershgorin step `1/L`, feasibility guard raises), `rebalance.py` (explicit raising `_SLEEVE_TO_RISK` map per §A.1, Σ/μ built once per §A.2, RC via one `portfolio_covariance` call at w\*, clip-dust→quantize→re-assert Σw=1 within 0.0001). `OptimizationResult` is now **frozen** with an additive `rebalance` field; `_optimizer_propose` carries it via `model_copy(update=…)` (v0 TLH `trades` unchanged — §B.1). Config pins `optimizer_config_version="2026.06"`, `risk_aversion_lambda=6.0`, `qp_tolerance=1e-9`, `qp_max_iters=5000` (λ is a **platform prior** §B.6). New dashboard panel "MV rebalance (target weights w\*)" off `general_hnw` rung-3 in-process (no DB), μ labelled "ex-ante class assumption". Falsifiers: `test_optimizer_qp` (zero-Δ, binding clip, λ-monotone, infeasible raise, Σ-built-once, Σw=1), `test_optimizer_mapping` (total + raises), `test_optimizer_rebalance` (universe union, RC rollup, advisory-no-trade, TLH coexistence, turnover_l1, policy_drift, illiquid/unbounded flags), `test_mu_not_named_forecast` + `test_optimizer_panel_shows_mu_source_label` (scan rendered copy), extended `test_pm_workflow`/`test_synthetic_ips_workflow`/`test_dashboard`/`test_messaging_handlers`. **Suite green: 340 passed.** Honest limitation: the rung-3 IPS bounds are tight enough that w\* is essentially bound-determined (λ-invariant on that fixture) — the λ-monotonicity property is therefore exercised at the `solve_qp` level with wide synthetic bounds, not on the real fixture. |
| 2026-06-28 | **po1-tax staged-estimator decision (Claude, plan-only).** Split the gated after-tax μ overlay into a **seam now** + **estimates later** so $0 tax unblocks the whole non-tax pipeline (po2 stress, execution, reporting, end-to-end stress testing) without faking honesty #5. Added **§14 Addendum C** (authoritative for the po1-tax seam): a swappable `TaxEstimator` protocol with per-sleeve `sleeve_mu_drag` granularity (finer than the portfolio-level `evaluate_tax_scenario`), default `ZeroTaxEstimator` (identity overlay, `is_zero` marker). Key honesty call: under the $0 seam the overlay is an **identity** (after-tax μ ≡ pre-tax μ; TLH/gain-deferral/asset-location value all 0), so $0 completes the overlay's **structure, not its behavior** — **#5 stays `not_computed`** and flips to `computed` only at the `QuantileTaxEstimator` stage (ladder: Zero → Quantile → LLM, same upgrade-path ethos as ROUTE B → ROUTE A). Honesty matrix #5, §8 dependency block, and the §5 po1-tax row updated to reference the seam. Falsifier set pinned (C.4): zero-estimator no-op, #5-stays-not_computed, and a **non-zero-stub test that moves w\*** (proves the seam carries a drag without shipping tax magnitudes). No code this entry — design pinned before implementation (same discipline as B.8). |
| 2026-06-28 | **po2 scenario-robust stress overlay shipped (Claude).** Shipped **Option A** (§B.8 RECOMMENDED): a SECOND constrained MV QP under the version-pinned `high_risk` crisis-correlation Σ behind the existing `optimizer.propose` op — **no new atomic op** (`test_robust_no_new_ops` green; `pm.* == {pm.advise}`, `optimizer.* == {propose, persist}`). New `decision/optimizer/robust.py` (`compute_stress_overlay` re-enters `run_mv_rebalance` with the crisis priors and `compute_stress=False` to break the recursion → reuses `solve_qp`/the Σ-build/the turnover treatment **verbatim** on an alternate Σ). Additive frozen `RebalanceProposal` fields (`stress_regime`, `stress_target_weights`, `stress_delta_w` = w\*_stress − w\*_base, `regime_gap_l1` = ‖w\*_base − w\*_stress‖₁, `stress_objective_value`, `stress_risk_contributions`) — all defaulted so the frozen-registry sample + re-freeze stay green. **honesty matrix #8 FLIPPED** `not_computed` → computed; **#5 (after-tax μ) stays `not_computed`** (tax seam $0, untouched). Config pins `optimizer_stress_regime="high_risk"`; **`optimizer_config_version` stays `2026.06`** (base solve byte-identical — `test_base_path_byte_identical_to_po1`). Dashboard panel "MV rebalance (target weights w\*)" **replaces** "(base-regime Σ only)" with a live base-vs-stress side-by-side (Stress w\*, regime shift, Stress RC columns) + a regime-gap line that badges "material" at ‖Δw‖₁ ≥ 0.05. **Chose A over B/C**: A reuses the solver/Σ-build verbatim, is lightest, drops into `assumptions=`, flips #8 cleanly; C (scenario P&L via `evaluate_stress`) named as the richer upgrade, B (penalty `max_s w'Σ_s w`) as the single-objective alternative. **Limitations stated honestly:** (1) `high_risk` crisis-blends ρ toward 0.85 **and** scales vols ×1.4 — a crisis *regime*, not correlation-only (panel + docs say so); (2) bound-determined fixtures pin both optima → regime gap ~0, so the binding "stress ≠ base" acceptance runs on a slack-bound synthetic fixture (base LOW ρ vs crisis HIGH ρ), mirroring po0/po1's solve-level property tests. Falsifiers: `tests/test_optimizer_robust.py` (6 tests) + `test_optimizer_panel_shows_base_vs_stress`; `test_sigma_built_once` now isolates the base solve via `compute_stress=False` (the overlay adds a second `portfolio_covariance` call). **Suite green: 386 passed.** |
| 2026-06-28 | **po1 turnover-budget half shipped (Claude).** Hard `‖Δw‖₁ ≤ τ` cap behind the existing `optimizer.propose` op — **no new atomic op** (`test_turnover_no_new_ops` green; `pm.* == {pm.advise}`, `optimizer.* == {propose, persist}`). **Shipped ROUTE B** (budget-scaled convex step `w_budget = w_current + (τ/‖Δw‖₁)·(w*−w_current)`) over ROUTE A (Dykstra L1-ball projection): B matches the staged-heuristic ethos, is exact on the budget (`‖Δw‖₁ = τ`), and preserves every po0 invariant cheaply on a box-feasible `w_current`; **A named as the documented upgrade**. Additive frozen fields on `RebalanceProposal`: `turnover_budget`, `turnover_binding`, `unconstrained_turnover_l1` (the "capped from X to τ" story) — all defaulted so the frozen-registry sample and re-freeze test stay green. `turnover_budget_pct is None` is a **strict no-op** (every po0 field byte-identical; existing po0 suite untouched and green). Dashboard flips the turnover line "reported" → "within budget"/"capped at budget" with pre-cap vs post-cap when it binds; demo-only budget pin `optimizer_demo_turnover_budget_pct=0.15` injected by the loader (`model_copy` on the IPS), labelled "demo". **Limitations stated honestly:** (1) `‖Δw‖₁` is **two-way** turnover; (2) `turnover_budget_pct` is "annual" in the IPS but po1 treats it as a **per-rebalance** cap; (3) when `w_current` breaches the IPS box, `w_budget` is projected back onto box ∩ simplex (`project_capped_simplex`) and turnover can drift slightly off `τ` — visible on the demo rung-3 fixture (capped 0.217 → 0.157 vs τ=0.15). **`optimizer_config_version` stays `2026.06`** — the solver/objective are unchanged; the budget adds an optional convex projection that is a no-op without a budget. **After-tax μ overlay (#5) and the analyst μ-tilt remain deferred as "po1-tax", gated on the tax estimate engine** (tax leg pinned $0; honesty #5 stays `not_computed`, not faked). **Suite green: 375 passed.** |
| 2026-06-28 | **Addendum review fixes (Claude).** Six corrections: (1) B.5 illiquid flag is **sleeve-level, not magnitude-gated** — dropped the `\|Δw\| > qp_tolerance` predicate that contradicted `test_illiquid_sleeve_flagged` and the zero-Δ probe. (2) A.2 — po0 builds `SleeveRiskState`/`AllocationSlot` directly and never constructs an `AssetPortfolio`, so its sum=1 validator is **not** in the path; made the `Σw=1` re-assertion an explicit po0 guard and added a **clip-float-dust-into-`[w_min,w_max]`** step (avoids `AllocationSlot.weight ge=0/le=1` raises). (3) Freezing `OptimizationResult` blocks post-hoc `result.rebalance = …`; §5/§B.1/risk-table now specify **construct-with-`rebalance=` or `model_copy(update=…)`**. (4) `test_mu_not_named_forecast` retargeted to **scan rendered copy** (the single-value `mu_source` Literal is trivially safe by typing; mirrors analyst `test_residual_not_named_alpha`). (5) projection citation corrected — capped-simplex / continuous quadratic-knapsack (Held–Wolfe–Crowder / Pardalos–Kovoor); Michelot 1986 is unit-simplex-only. (6) coined "PM enrich-1" → grounded "PM axiom enrichment (Addendum C)". No code; suite green. |
