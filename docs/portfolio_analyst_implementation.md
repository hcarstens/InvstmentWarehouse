# Portfolio Analyst — Implementation Plan

**Status:** pa0 planned (drafted from PM milestone — attribution first, thesis/NPA follow)
**Date:** 2026-06-28
**Owner:** decision plane / `warehouse.decision.analyst` (new sub-package)
**Inputs:** [`heuristics/Mental Model of The Portfolio Analyst.md`](heuristics/Mental%20Model%20of%20The%20Portfolio%20Analyst.md) (ℍ_PortfolioAnalyst — 7-checkpoint epistemology),
[`portfolio_manager_implementation.md`](portfolio_manager_implementation.md) (§3 leg model, §4 `not_computed` honesty rule, §12 next milestone),
[`messaging_protocol.md`](messaging_protocol.md) (§5 catalog, S1 atomic-op rule),
[`research/hnw_portfolios.md`](research/hnw_portfolios.md) (graph axiom, cohorts, rung ladder),
[`heuristics/Mental Model of The Portfolio Manager.md`](heuristics/Mental%20Model%20of%20The%20Portfolio%20Manager.md) (axiom 1 — attribution feeds the PM unit-of-account),
[`dev_contract_registry.md`](dev_contract_registry.md) (`portfolio_analyst` track)

---

## 1. Principle — decompose return into explained vs unexplained

The Portfolio Analyst is the **position-level research-and-attribution framework**, not an
allocation engine. Its job is to **reconcile every return to an explained source** and surface
the **unexplained residual as unidentified risk** (ℍ_PortfolioAnalyst axiom 1). It is advisory
and pure: it never mutates, never trades. Kill-criteria and NPA flags raise **alerts to the
advisor**, never autonomous sells — the human gate dominates (CLAUDE.md).

| Layer | Package / `op` | Role | Kind |
| --- | --- | --- | --- |
| **Portfolio Manager** | `decision.pm` → `pm.advise` | Whole-book coordinator; consumes the analyst leg | EVALUATE composite |
| **Portfolio Analyst** | `decision.analyst` → `attribution.evaluate` | Per-position P&L decomposition + residual | EVALUATE |
| **Portfolio Analyst** | `decision.ips` → `policy.check` | Drift + concentration (**already live**) | EVALUATE |

```text
PORTFOLIO MANAGER                       PORTFOLIO ANALYST (position-level, pure)
pm.advise ──┬── risk.evaluate
            ├── policy.check        (drift + concentration — live today)
            ├── attribution.evaluate  ◄── NEW atomic leg (pa0)
            │     → PositionAttribution[]  (realized − class-expected = residual)
            ├── optimizer.propose
            └── tax.scenario        (held at $0 — flow-test enabler)
        → score_pm_axioms → PmNarrative
        (analyst-side: score_analyst_checkpoints → AnalystReview)
```

**Why now (not the tax engine):** keeping `evaluate_tax_scenario → $0` lets synthetic
portfolios + IPS exercise the **whole flow** while we deepen the analyst signal. The analyst
output (residuals, kill breaches, NPA flags) is what gives **portfolio optimization** — the
genuinely hard downstream problem — a defensible objective and constraint set. The optimizer is
only as good as the analyst signal feeding it (`portfolio_manager_implementation.md` §12).

---

## 2. The honesty rule — applied by the model to itself

ℍ_PortfolioAnalyst is **defined by three negations**: ¬(single-path DCF), ¬(frequentist
inference), ¬(composite sufficiency). pa0 takes those negations literally **about its own
output**:

- **¬Composite Sufficiency → checkpoint 7 is a design invariant.** The attribution must never
  collapse to one un-decomposable score; `PositionAttribution` always exposes the components
  (class-expected vs residual), never just a number. A composite that hides its driver is
  banned by construction.
- **¬Single-Path / no-valuation gap → `not_computed`, never a faked `pass`.** Checkpoints that
  need an engine we don't have (valuation scenario range, factor loadings, out-of-sample
  validation) score `NOT_COMPUTED` — the exact Goodhart guard the PM plan uses for axiom 5, and
  the analyst's **own axiom 6 (Goodhart vigilance)** turned inward.
- **Residual is labelled "idiosyncratic + unexplained," never "alpha"** (axiom 1: unexplained
  residual is unidentified risk, not skill).

### 7-checkpoint computability (the honesty matrix)

| # | Checkpoint (mental model) | Computed from | pa stage |
| --- | --- | --- | --- |
| 1 | Thesis documentation + kill criteria | `PositionThesis` store | **pa1** — `not_documented` until then |
| 2 | **Attribution reconciliation** | realized return − class-expected over holding period = residual | **pa0 — scorable** |
| 3 | Valuation scenario range | — no valuation engine (shared gap w/ PM axiom 5) | **`not_computed`** |
| 4 | Out-of-sample validation | — no signal/screen pipeline yet | **`not_computed`** |
| 5 | Mechanism check | class beta is mechanism-near (one causal hop) | **pa0 — scorable (partial)** |
| 6 | Goodhart audit | reported-vs-economic divergence — no fundamentals feed | **`not_computed`** (applied to our own metrics) |
| 7 | Composite decomposition | attribution **is** the decomposition | **satisfied by design** (invariant) |

`AnalystCheckpoint` reuses the PM `AxiomScore` vocabulary: `PASS | WARN | BREACH |
NOT_COMPUTED`, plus `NOT_DOCUMENTED` for checkpoint 1 (thesis absent — first-class, not faked).

---

## 3. What is computable today (pa0 attribution mechanics)

From `LotPositionView` (`cost_basis`, `market_value`, `unrealized_gain`, `acquisition_date`,
`asset_class`, `liquidity_tier`) and `RiskAssumptions.class_expected_return` (shipped):

```text
holding_years      = (as_of_date − acquisition_date) / 365
realized_return    = unrealized_gain / total_cost_basis          # point-in-time, unrealized
realized_annual    = (1 + realized_return) ** (1/holding_years) − 1
class_expected     = class_expected_return[asset_class]          # the mechanism (asset-class beta)
residual_annual    = realized_annual − class_expected            # idiosyncratic + UNEXPLAINED
```

- **Attribution = `{class_expected, residual}` per position**, rolled up to a portfolio
  residual. Axiom 1: a large/growing residual is the early-warning instrument.
- **Mechanism (checkpoint 5):** the asset-class expected return is one causal hop from the
  driver → `PASS` partial. Factor-level mechanism is unavailable → that sub-component is
  `not_computed`, never invented.

**Stated limitations (honesty, surfaced in the report and dashboard):** unrealized only (no
realized lots / income / dividends), point-in-time (no intra-period path), class-beta not full
factor (Brinson) attribution. This is a **first-cut beta decomposition**, labelled as such.

**Walk-forward safe:** uses only as-of data (`acquisition_date ≤ as_of`, current marks); no
lookahead (CLAUDE.md walk-forward discipline).

---

## 4. Scope — what ships vs deferred

### In scope (pa0–pa2)

| Item | Rationale |
| --- | --- |
| `evaluate_attribution(positions, assumptions, *, as_of) → AttributionReport` | The analyst value-add — axiom 1 residual decomposition |
| **One** new atomic op `attribution.evaluate` (EVALUATE, pure) | Distinct concern from drift; reached via dispatch (registry = indirection) |
| `score_analyst_checkpoints(report, theses) → AnalystReview` (7-checkpoint, honest gaps) | The analyst diagnostic — analog of `score_pm_axioms` |
| Additive `AdviceBundle.attribution` — PM nest-dispatches a 5th leg | PM consumes the signal; contract additive (like `narrative`) |
| `PositionThesis` model + store + `evaluate_kill_criteria` (pa1) | Axiom 2 — falsifiable thesis, monitored not just P&L |
| `flag_non_performing(positions, alts, ips) → NpaFlags` (pa2) | Open question #13 — drawdown, stale marks, missed calls, liquidity |
| Freeze + register `AttributionReport`, `PositionAttribution`, `AnalystReview`, `PositionThesis`, `NpaFlags` | Audit/replay-critical |
| Dashboards: attribution residual table (pa0), kill-criteria watch (pa1), NPA panel (pa2) | Dashboard-first |
| Version-pin thresholds → `analyst_config_version` | Audit replay (mirrors `pm_axiom_config_version`) |
| Falsifier tests + advance `portfolio_analyst` track rows | Contract discipline |

### Deferred

| Item | Why |
| --- | --- |
| Factor-model attribution (Brinson, multi-factor loadings) | No factor engine — checkpoint sub-component `not_computed`, not faked |
| Valuation scenario ranges (bear/base/bull, terminal sensitivity) | No valuation engine (same gap as PM axiom 5) |
| Out-of-sample / walk-forward signal validation | No quant screen pipeline yet |
| Realized-lot + income/dividend attribution | pa0 is unrealized point-in-time; enrich the backing function later |
| NPA flags as **optimizer constraints** | v0 flags feed the **approval gate only**, not autonomous constraints (human gate) |
| Autonomous kill-criteria sells | Alerts only — advisor decides |
| LLM thesis interpreter / narrative | Open question (`TODO.md`) |

---

## 5. Migration slices — PR sequence + acceptance

No new package sprawl: `warehouse.decision.analyst` holds `attribution.py`, `thesis.py`,
`npa.py`, `review.py`. The new op's handler stays a thin `(ctx, payload)` wrapper in
`messaging/handlers.py` that calls into `decision.analyst`.

### pa0 — attribution + residual *(~1 PR)*

**Goal:** `attribution.evaluate` returns per-position `{class_expected, residual}`; PM attaches it.

| Task | File(s) |
| --- | --- |
| `PositionAttribution`, `AttributionReport`, `AnalystCheckpoint`, `AnalystReview` | `decision/analyst/models.py` *(new)* |
| `evaluate_attribution(...)` (residual mechanics §3; factor sub-component `not_computed`) | `decision/analyst/attribution.py` *(new)* |
| `score_analyst_checkpoints(report, theses=None)` (checkpoint 2 scorable, 5 partial, rest honest gaps) | `decision/analyst/review.py` *(new)* |
| `AttributionEvaluatePayload`; register `attribution.evaluate` (EVALUATE) | `messaging/payloads.py`, `messaging/handlers.py` |
| Additive `AdviceBundle.attribution`; `_pm_advise` nest-dispatches the 5th leg | `messaging/payloads.py`, `messaging/handlers.py` |
| `analyst_config_version` + residual WARN/BREACH thresholds | `config.py` |
| Register frozen types | `integrity/frozen_registry.py`, `tests/test_frozen.py` |

**Acceptance:**

- A position with `realized_annual ≈ class_expected` → `|residual|` near zero → checkpoint 2 `PASS`.
- A divergent position → nonzero residual → checkpoint 2 `WARN`/`BREACH`; report orders by `|residual|`.
- `review.checkpoints["checkpoint_3"] == NOT_COMPUTED` (no valuation engine); checkpoint 7 always satisfied (components present).
- `bundle.attribution is not None`; `test_pm_no_new_ops` still green (`pm.* == {pm.advise}` — the new op is `attribution.*`, an analyst op).
- `pytest tests/test_frozen.py` green.

### pa1 — thesis + kill criteria *(~1 PR)*

**Goal:** every position carries a falsifiable thesis with pre-specified kill criteria; breaches alert.

| Task | File(s) |
| --- | --- |
| `PositionThesis` (frozen, effective-dated): mechanism, `kill_criteria` (drawdown-vs-cost, residual cap, liquidity floor, horizon) | `decision/analyst/thesis.py` *(new)* |
| Thesis store keyed account×instrument | `decision/analyst/thesis.py` |
| `evaluate_kill_criteria(position, thesis) → list[KillBreach]` (alerts, **never sells**) | `decision/analyst/thesis.py` |
| Synthetic theses emitted with households (flow-testable) | `research/synthetic/...` |
| Checkpoint 1 flips `not_documented → PASS/BREACH` when a thesis exists | `decision/analyst/review.py` |
| Kill-criteria watch panel | `dashboard/render_analyst.py` |

**Acceptance:**

- Position with no thesis → checkpoint 1 `NOT_DOCUMENTED` (not a faked pass).
- Synthetic thesis with a drawdown kill at −20%, position at −25% → one `KillBreach` alert; **no order staged**.
- Kill criteria written **before** the position date (axiom 2: pre-committed, no hindsight).

### pa2 — non-performing-asset flags *(~1 PR)*

**Goal:** surface NPAs across positions + alternatives (open question #13).

| Task | File(s) |
| --- | --- |
| `flag_non_performing(positions, alts, ips, *, as_of) → NpaFlags` with reason codes | `decision/analyst/npa.py` *(new)* |
| Rules (version-pinned): sustained drawdown vs cost, stale alt mark (`last_mark_date` age), missed capital call, IPS liquidity breach | `decision/analyst/npa.py`, `config.py` |
| NPA flags feed **approval queue only** (not optimizer constraints in v0) | `decision/analyst/npa.py` |
| NPA panel across positions, alternatives, manifest | `dashboard/render_analyst.py` |

**Acceptance:**

- Alt with `last_mark_date` older than `analyst_stale_mark_days` → stale-mark NPA flag.
- Position below cost beyond drawdown threshold for the sustained window → NPA flag with reason code.
- Flags appear on the dashboard; **none** auto-modify the optimizer or stage trades.

---

## 6. Protocol & boundary invariants — acceptance matrix

| Invariant | Source | Test |
| --- | --- | --- |
| Analyst legs are pure — never read `ctx.session` for mutation | messaging §4.1 | `test_attribution_evaluate_pure` |
| Exactly **one** new atomic op (`attribution.evaluate`); no analyst *coordinator* op | messaging S1 | `test_no_analyst_coordinator_op` |
| Residual labelled idiosyncratic+unexplained, never "alpha" | analyst axiom 1 | `test_residual_not_named_alpha` |
| Valuation/factor checkpoints `not_computed`, never faked | analyst axiom 6 (Goodhart) | `test_analyst_gaps_not_computed` |
| Attribution always decomposable (no hidden composite) | analyst ¬M7 | `test_attribution_components_present` |
| Kill-criteria + NPA raise alerts, never stage trades | human-gate (CLAUDE.md) | `test_kill_criteria_no_persist`, `test_npa_no_persist` |
| `correlation_id` threads PM → attribution leg | messaging §4.1 | `test_pm_attribution_correlation` |
| PM op surface unchanged (`pm.* == {pm.advise}`) | PM §6 | `test_pm_no_new_ops` (existing) |
| Walk-forward — attribution uses only as-of data | CLAUDE.md | `test_attribution_walk_forward` |

---

## 7. Test plan summary

| File | Covers |
| --- | --- |
| `tests/test_analyst_attribution.py` | residual mechanics, ordering, components-present, walk-forward |
| `tests/test_analyst_review.py` | 7-checkpoint scoring, `not_computed`/`not_documented` honesty |
| `tests/test_analyst_thesis.py` | kill-criteria breach → alert, no persist, pre-committed dates |
| `tests/test_analyst_npa.py` | stale marks, drawdown, missed calls; no optimizer mutation |
| `tests/test_pm_workflow.py` | *(extend)* PM bundle carries `attribution` on demo + HNW rung 3 |
| `tests/test_dashboard.py` | *(extend)* attribution residual table; NPA panel |
| `tests/test_frozen.py` | analyst frozen types immutable |

**CI gate:** attribution residual correctness + checkpoint honesty + no-persist (kill/NPA) +
PM op-surface unchanged.

---

## 8. Dependencies & build order

```text
synthetic IPS si2 (bundle) + risk assumptions (class_expected_return)  [shipped]
  └─ pa0 (attribution + residual; PM 5th leg)        [planned — NEXT]
       └─ pa1 (thesis + kill criteria)               [planned]
            └─ pa2 (non-performing-asset flags)      [planned]
                 └─ portfolio_optimization v1        [planned — hard problem]

Held on purpose (non-blocking):
  tax estimate engine  →  flips tax leg $0 → live (no analyst change)
```

**Depends on:** messaging m1, PM pm0–pm2 (shipped), synthetic IPS si2, risk assumptions.
**Does not depend on:** tax estimate engine, QP/MIP optimizer, valuation engine, Phase 5.

---

## 9. HNW fixture matrix (acceptance households)

| Fixture | Source | Exercises |
| --- | --- | --- |
| Demo seed | `DEMO_HOUSEHOLD_ID` | End-to-end attribution panel + PM 5th leg |
| `general_hnw` rung 3 | `emit_synthetic_household` → `lot_positions_from_fixture` | 5-sleeve residual spread, liquidity tiers |
| `founder_executive` rung 4 | same | Concentrated lot → large residual + NPA candidate |
| `concentrated_stress` | SDG2 negation | Drawdown NPA flags; kill-criteria breach |
| **zero-residual probe** | synthetic position with `realized ≈ class_expected` | Checkpoint 2 `PASS` falsifier *(add knob if absent)* |

Reuses the PM in-process path (`lot_positions_from_fixture`); demo uses DB bootstrap. Synthetic
theses (pa1) emitted alongside households so kill-criteria are flow-testable without DB.

---

## 10. Doc updates on ship

| Doc | Update |
| --- | --- |
| [`dev_contract_registry.md`](dev_contract_registry.md) | `portfolio_analyst` track rows pa0–pa2; `warehouse.decision.analyst` boundary; `attribution.evaluate` in op catalog |
| [`messaging_protocol.md`](messaging_protocol.md) | §5 catalog: add `attribution.evaluate` (one new atomic EVALUATE op) |
| [`portfolio_manager_implementation.md`](portfolio_manager_implementation.md) | §3 note: `AdviceBundle.attribution` 5th leg; optional PM axiom 1 upgrade to residual-based |
| [`TODO.md`](../TODO.md) | Flip pa0–pa2 rows shipped; NPA cross-refs open question #13 |

---

## 11. Self-review

### Strengths

- **Honest by construction** — the analyst's own ¬M7 (anti-composite) and Goodhart axiom are
  applied to its *own* output: residuals are decomposed, gaps are `not_computed`, residual is
  never relabelled "alpha." Mirrors the PM `not_computed` rule.
- **Computable first cut** — attribution ships real numbers from shipped data (cost basis,
  marks, `class_expected_return`), not a stub; limitations are surfaced, not hidden.
- **Minimal abstraction** — one new atomic op; analyst reached via dispatch; PM contract additive.
- **Advisory/acting split preserved** — kill criteria + NPA alert only; no autonomous trades.
- **Unlocks the hard problem** — residuals + kill breaches + NPA flags are the optimizer's
  objective/constraint inputs; tax held at `$0` keeps the flow stress-testable throughout.

### Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Residual misread as skill/alpha | Labelled "idiosyncratic + unexplained"; `test_residual_not_named_alpha` |
| Unrealized/point-in-time attribution overclaims | Limitations stated in report + dashboard; flagged as beta first-cut |
| New op proliferation | Exactly one atomic op (`attribution.evaluate`); no analyst coordinator (`test_no_analyst_coordinator_op`) |
| Kill criteria fitted after the fact | Effective-dated thesis; pre-position-date assertion (axiom 2) |
| NPA flags silently constrain optimizer | v0 flags feed approval gate only; `test_npa_no_persist` |
| `AdviceBundle` churn | Additive `attribution` field; frozen locks the rest |

### Verdict

**Ready to execute** starting with pa0 (attribution). Estimated **3 PRs**. Critical path:
**pa0 → pa1 → pa2 → optimization v1**. pa0 alone materially upgrades the PM signal.

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-06-28 | Initial draft (Claude). Grounded against shipped code: `LotPositionView` (cost/marks/acq-date), `RiskAssumptions.class_expected_return`, `AlternativeHoldingView.last_mark_date`, live `policy.check`. Attribution-first ordering per `portfolio_manager_implementation.md` §12 (tax held at `$0` as flow-test enabler). Honesty matrix maps the 7 mental-model checkpoints to computability; one new atomic op (`attribution.evaluate`); PM gets additive 5th leg. |
