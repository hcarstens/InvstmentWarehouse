# PM Pivot — from Wealth Management to Portfolio Management

**Status:** proposed (north-star reframe; no code yet)
**Date:** 2026-07-02
**Owner:** whole repo — decision plane leads, all five planes touched
**North-star lens:** [`heuristics/Mental Model of The Portfolio Manager.md`](../heuristics/Mental%20Model%20of%20The%20Portfolio%20Manager.md)
(ℍ_Allocation) — allocation-and-survival; the portfolio is the unit of account
(axiom 1); rebalance on calibrated, continuously-updated evidence (axiom 7 /
Forecasting F8). **Judgment companion:** [`heuristics/Persona of The Portfolio Manager.md`](../heuristics/Persona%20of%20The%20Portfolio%20Manager.md)
— apply on the judgment slices (pv1 view-weighting, pv3 survival sizing, pv5
concentrate-vs-diversify), not on the reframe.
**Goal (concrete):** monitor the daily statistical movements of a book and
generate **Bayesian updates** of the portfolio's beliefs, then re-optimize
weights against those posteriors — the traditional hedge-fund PM loop
(cf. [The-FIIJ](https://github.com/hcarstens/The-FIIJ)).
**Companion (stepped build):** [`pm_pivot_plan_implementation.md`](../pm_pivot_plan_implementation.md)
(pv0–pv4).
**Code-review debt this pivot closes:** [`code_review_claude_2026-06-30.md`](../code_review_claude_2026-06-30.md)
C1 (red mypy), M1/M2 (frozen records), M3 (dead walk-forward guards), M4
(plane logic in dashboard) — each is a guard rail the new belief loop must
build correctly, so the pivot pays down review debt as a side effect.

---

## 1. The thesis — the shape already fits; swap the objective and add one engine

Investment Warehouse is a **wealth-management** platform: north star *after-tax
wealth maximization* over a household/entity graph, with the tax overlay (TLH,
asset location, wash chains, trusts) as the differentiating machinery.

A hedge-fund **Portfolio Manager** runs a different loop but the *same
plumbing*: observe today's statistical moves → update beliefs → re-optimize the
book → check against mandate and risk limits → report. That maps almost 1:1
onto the existing five planes and the daily-refresh workflow. **This is a
reframe plus one genuinely new engine (Bayesian belief updating) — not a
rebuild.** ~80% of the code carries over unchanged.

Crucially, a **Bayesian posterior is a replay record**: prior + views in, a
versioned posterior out, immutable and reproducible. So the new engine is
*native* to this repo's frozen-registry / version-pinning / walk-forward
discipline — it exercises exactly the guard rails the 2026-06-30 review flagged
as declared-but-not-enforced.

---

## 2. The north-star swap

| | Wealth Mgmt (now) | Portfolio Mgmt (target) |
| --- | --- | --- |
| **Objective** | After-tax wealth maximization | Risk-adjusted active return (IR / geometric growth) under a daily belief loop |
| **Unit of account** | Household / entity graph | **Book / strategy / portfolio** (persona axiom 1) |
| **Contracts** | IPS, mandates, fee schedules | **Fund mandate + risk limits** — reuse the effective-dated contract machinery verbatim |
| **Daily workflow** | custodian → reconcile → lots → corp actions → exceptions | **market data → daily stats → Bayesian update → drift vs targets → alert queue** |
| **Optimizer input** | tax-aware μ (TLH, asset location) | **posterior μ** (Black–Litterman: prior ⊕ views) into the *same* constrained-MV QP |
| **Differentiator** | tax overlay | **calibrated daily belief updating** — the FIIJ loop |
| **Secondary (quarantined)** | (was primary) tax lots, wash sales, trusts, asset location | optional `warehouse.wealth` module; tests kept green |

The persona's negations set the discipline: **¬RM4** (maximize geometric growth
/ survival, not arithmetic EV — size below the naive Kelly optimum), **¬PS2**
(correlations are regime-dependent — diversification fails in crises, so
stress the covariance), **¬Opt3** (the frontier is non-convex and drifting —
robust and simple beats an over-fit optimum). These are already partly encoded
(po2 crisis-Σ overlay, box-constraint diversification floors); the pivot makes
them the *headline*, not a caveat.

---

## 3. The heart to build — a daily Bayesian belief loop

Two new engines, both **in-plane** (dashboard consumes, never orchestrates —
fixes review M4):

### A. Daily statistics engine — `warehouse.research.stats`
The "monitor daily statistical movements" half.
- Return series, EWMA & realized vol, rolling covariance / correlation,
  factor / beta exposures.
- **Move significance** — z-score of today's move vs its conditional
  distribution ("signal or noise?"); this is the evidence the belief update
  consumes.
- P&L attribution by position and by factor.
- Walk-forward safe by construction — **this is where the two dead guards
  (`assert_scenario_observations_not_after`, `assert_series_cutoff`, review M3)
  finally get wired**, because it is the first real time series in the repo.
- **New data requirement:** a price *history* table. Today `MarketPriceRow` PK
  is `security_id` alone (one mark per security — review M3 caveat); daily
  stats need `(security_id, as_of_date)`. This is the one real ingest addition.

### B. Belief / Bayesian-update engine — `warehouse.decision.beliefs`
The "generate Bayesian updates" half. **Method v0: Black–Litterman** — the
canonical PM framework and the one that plugs straight into the shipped QP.

- **Prior μ** = equilibrium / strategic prior. v0 reuses the shipped
  `assumptions_for("base").class_expected_return` (the risk plane's version-
  pinned `CLASS_EXPECTED_RETURN`) as the prior — *no new data needed to ship
  the loop's structure.*
- **Views** = confidence-weighted statements (a sleeve tilt, a momentum /
  mean-reversion signal). **The first live views come from
  [The-FIIJ](https://github.com/hcarstens/The-FIIJ)** — its daily
  `finance_view_history.json` is already a time series of directional,
  z-score-valued signals with a regime label, and its `oos/` scorecards carry
  Brier calibration. We ingest FIIJ signals as `signal`-sourced views (confidence
  from FIIJ's own calibrated probabilities) — we do **not** fabricate our own
  alpha (see §6). A discretionary `manual` override path exists for demo/testing.
- **Posterior μ** = BL blend of prior and views by confidence → fed directly
  into `run_mv_rebalance` (the po0 QP) as its μ input.
- **New frozen, registered records** (fixes review M1/M2 by building them right
  from day one): `PriorBelief`, `View`, `PosteriorBelief`, and `BeliefUpdate`
  `(prior_id, view_set, posterior_id, method, config_version, timestamp)` — the
  canonical **belief-journal entry / replay fingerprint** (the FIIJ "journal").

The two engines compose: daily stats produce evidence → the belief engine turns
evidence into a posterior → the QP turns the posterior into target weights → the
mandate/limit monitor (reused IPS monitor) scores drift → the dashboard shows
the day. That closed loop *is* the product.

### First live data source: The-FIIJ

The pivot's first real inputs are not custodian files — they are **FIIJ's daily
forecast outputs**. FIIJ is a daily 30-day econometric + geopolitical forecast
engine over equities / commodity ETFs / crypto that already does the "monitor
daily movements → produce a scored view" transform we would otherwise build from
scratch. It hands us, per day:

| FIIJ artifact | Feeds | Maps to |
| --- | --- | --- |
| `data/finance_view_history.json` | belief engine views | `View` (source `signal`); `sheets[].signals[].value` = z-score-valued directional view; `detail` carries raw `z=` scores |
| `regime_label` / `regime_class` on each snapshot | Σ regime selection | base vs crisis Σ in the BL blend (¬PS2 / po2 — a regime read *for free*) |
| `data/breakouts.csv` | per-ticker signals | instrument-level views (rolled up to sleeves) |
| `data/calibrated_thresholds.json` + `oos/` Brier scorecards | view confidence + belief-journal calibration | `View.confidence` (Ω); Forecasting-F8 calibration leg |
| `data/equity_curve.csv` + `oos/*_trades.csv` | realized P&L | attribution / calibration ground truth |

So FIIJ collapses two risks at once: it supplies the signal pipeline (views are
`signal`-sourced from day one, not `manual`) **and** a ready-made calibration
history — meaning the belief loop can be scored (axiom 7 / F8) far sooner than a
from-scratch build would allow. The daily-stats engine's remaining job is the
*portfolio-side* math on our own positions (return, vol, attribution) that FIIJ,
a signal engine, does not compute for a specific book.

---

## 4. Plane-by-plane — what changes, what carries over

| Plane | Carries over unchanged | Changes / adds |
| --- | --- | --- |
| **Data** (`warehouse.data`) | Ledger, security master, positions, reconciliation | **+ price history time series**; custodian ingest reframed as book marks; entity graph becomes optional |
| **Research** (`warehouse.research`) | Risk engine (`evaluate_risk`), covariance/Σ, backtest harness, walk-forward guards | **+ daily statistics engine** (returns, vol, corr, move-significance, attribution); **wire M3 guards** |
| **Decision** (`warehouse.decision`) | Optimizer QP (`run_mv_rebalance`, po0–po2), IPS monitor → **mandate/limit monitor**, `pm.advise` coordinator | **+ Bayesian belief engine** (Black–Litterman); posterior μ replaces static class μ into the QP |
| **Execution** (`warehouse.execution`) | OMS, reconciliation, staged orders, approval gates | Reframe "rebalance advisory" as the daily book rebalance; human gate unchanged |
| **Reporting** (`warehouse.reporting`) | Performance & risk reporting | **+ belief-journal / calibration report** (were our forecasts scored? — Forecasting F8) |

**Quarantined, not deleted:** tax scenarios, wash chains, TLH, asset location,
trusts/beneficiaries move into an optional `warehouse.wealth` package. The tax
leg is *already* an intentional `$0` stub across pm/po plans, so this mostly
formalizes an existing boundary. Suite stays green.

---

## 5. Sequencing (dashboard-first — every slice ships a panel)

Full stepped detail in [`pm_pivot_plan_implementation.md`](../pm_pivot_plan_implementation.md).

| Slice | Ships | Panel |
| --- | --- | --- |
| **pv0** | Reframe: north star, `Book`/`Portfolio` unit, mandate/limit vocab (docs + registry only) | Catalog retheme (`/`) |
| **pv1** | Belief engine — Black–Litterman v0; posterior μ → existing QP; frozen belief records (demo/manual views) | `/decision` → **Belief Journal** |
| **pv2** | **FIIJ ingest adapter** (finance-view + regime + calibration) → live `signal` views; portfolio-side daily stats; wire M3 guards | `/research` → **Daily Movements** + FIIJ feed |
| **pv3** | Close the loop — FIIJ views → posterior update → QP → limit/drift alert queue; regime-conditional Σ from FIIJ `regime_class`; calibration from FIIJ OOS | `/execution` or `/` → **PM Daily Cockpit** |
| **pv4** | Quarantine wealth machinery into `warehouse.wealth`; fix C1 (red mypy) | Wealth panels move behind a nav toggle |
| **pv5** (later) | Hierarchical layer (option 3): sleeve QP top-down + FIIJ within-sleeve name selection — recovers the discarded cross-sectional edge | `/decision` → **Name-Selection** panel |

**pv3 is the live proof-of-concept.** pv0→pv3 is the critical path to the
biggest immediate demonstration: FIIJ's real daily file in → posterior belief →
proposed rebalance → limit alerts, live on the dashboard, scored against FIIJ's
own calibration. It deliberately uses the **sleeve rollup** (decision 4) so the
existing QP is reused unchanged — simplest thing that proves the whole loop
works end-to-end on live data. pv4 cleans up; **pv5 comes after the PoC lands**
and is where FIIJ's name-picking edge is recovered via the hierarchical layer.

Rationale for the order: pv0 is pure docs (cheapest, sets the north star); pv1
ships the *distinctive* engine first while reusing the QP (fastest path to
visible Bayesian output); pv2 adds the FIIJ feed + daily-monitoring data the loop
feeds on; pv3 fuses them into the live PoC; pv4 cleans up; pv5 deepens. Each
slice is independently shippable and green.

---

## 6. What we deliberately do **not** do (honesty rule)

Following the house `not_computed` discipline (never fake a computed value):

- **We do not fabricate alpha — we ingest FIIJ's.** The signal pipeline is
  external (FIIJ); the warehouse's belief engine *consumes* FIIJ views and their
  FIIJ-supplied calibration, and never invents a forecast the source did not
  make. FIIJ's own honesty (equity-only live because it is the only path with
  validated OOS Brier calibration) is preserved: a FIIJ signal whose OOS
  calibration is failing is ingested as a *low-confidence* view, never upgraded
  (PO6 + persona ¬Opt3 — the optimizer amplifies input error).
- **No autonomous trading.** The loop is advisory; the human approval gate
  dominates (persona axiom 6 — control exposure, not outcomes).
- **No claim of calibrated forecasts until they are scored.** Calibration
  (F8 / persona axiom 7) is `not_computed` until pv3's belief journal has a
  realized-vs-forecast history to score against.
- **No deletion of the tax/wealth machinery** — quarantined and kept green, so
  the after-tax overlay can return as a *sleeve* of the objective later.

---

## 7. Decisions (resolved — recommendations, given the FIIJ data source)

The three forks are resolved below and baked into the implementation plan. Each
recommendation is reinforced by the FIIJ context (a pure single-book equity
signal engine with no tax/entity structure).

1. **Wealth machinery → quarantine into optional `warehouse.wealth` (not
   delete).** FIIJ carries no household, entity, or tax structure, so the wealth
   overlay is dead weight on the first live path — but the after-tax overlay
   stays valuable as a *future objective term* once a taxable book is modelled.
   Quarantine keeps tests green and preserves that option. **Rec: quarantine.**

2. **Bayesian method → Black–Litterman, with FIIJ finance-view signals as the
   view inputs (not manual, not a home-grown Kalman tracker).** BL is still the
   right blend because it produces a posterior μ that feeds the po0 QP with *no
   optimizer change*. The reason to prefer it over a conjugate Normal–Normal /
   Kalman return-tracker is now decisive: **FIIJ already performs the
   daily-statistics→signal transform** (z-score-valued directional views + a
   regime label + Brier calibration), so the tracker would be re-deriving work
   FIIJ hands us. FIIJ signals become the BL view matrix (P/Q), FIIJ calibrated
   confidence becomes Ω, and FIIJ's `regime_class` selects base vs crisis Σ. A
   Kalman/EWMA layer is deferred to *smoothing* FIIJ inputs if noise demands it,
   not as the primary engine. **Rec: Black–Litterman fed by FIIJ.**

3. **Unit rename → thin `Book`/`Portfolio` alias over the existing working set
   (not a global `household_id` rename).** FIIJ is one equity book on Alpaca; the
   first live path needs exactly one book's positions and signals. A thin
   additive alias suffices; a repo-wide `household_id` rename is deferrable,
   mechanical churn with no first-path payoff. **Rec: thin alias.**

4. **FIIJ granularity → roll FIIJ signals up to the 6 sleeves for v0; add a
   hierarchical name-selection layer later; never naïve N×N instrument MV.** The
   priority is the **simplest, biggest, immediate proof of a live concept** — so
   v0 nets FIIJ's per-name/macro signals into per-sleeve tilts and feeds the
   existing 6-sleeve QP unchanged. This is the fastest path from "FIIJ emits a
   file" to "the dashboard shows a live posterior + rebalance." It **discards
   FIIJ's cross-sectional (name-picking) edge** — stated plainly on the panel,
   not hidden. **Later (pv5, option 3): a two-layer hierarchical build** — the
   sleeve QP sets top-down allocation, a within-sleeve layer fed by FIIJ
   breakouts drives name selection — which recovers the dispersion edge *without*
   asking one MV optimizer to solve a 100×100 problem. **Full naïve
   instrument-level MV is rejected** (PO6 / persona ¬Opt3 — a large-N covariance
   is an estimation-error trap the optimizer amplifies). **Rec: sleeve rollup
   now, hierarchical layer as pv5.**

---

## 8. Self-review

### Strengths
- **Reuses ~80%** — QP, risk engine, IPS monitor, frozen registry, dashboard
  shell, version-pinning, error-bubbling all carry over; the pivot adds two
  engines and one data table.
- **Pays down review debt** — the belief records are built frozen+registered
  (M1/M2), the daily-stats time series wires the dead guards (M3), the engines
  live in-plane (M4), and pv4 fixes the red gate (C1).
- **Honest by construction** — views, calibration, and the signal pipeline are
  `not_computed` until real; nothing is faked.
- **Persona-aligned** — the loop *is* axiom 7 (rebalance on calibrated
  evidence); survival/¬RM4 sizing and ¬PS2 crisis-Σ are already partly shipped.

### Risks & mitigations
| Risk | Mitigation |
| --- | --- |
| Belief loop becomes theater (views with no signal) | v0 views labelled `manual`; calibration `not_computed` until scored — no fabricated forecast |
| Price-history table reopens the M3 join hazard | pv2 wires `assert_series_cutoff` on the new time series before any stats read it |
| Household→Book rename churn | Thin alias over the existing working set (open decision 3), not a global rename |
| Wealth quarantine breaks tests | pv4 moves modules with tests attached; suite stays green as an acceptance gate |
| BL prior mis-specified (equilibrium ≠ CLASS_EXPECTED_RETURN) | v0 labels the prior an *ex-ante class assumption*, not equilibrium; reverse-optimization prior is a documented pv1+ upgrade |

### Verdict
**Ready to sequence.** pv0 (reframe docs) → pv1 (Black–Litterman belief engine
on the existing QP) is the critical path to a visible daily Bayesian loop; pv2–pv3
add the monitoring data and fuse the loop; pv4 cleans up. The distinctive
engine (Bayesian updating) is shippable in pv1 with **no new market data** by
reusing the shipped sleeve μ/Σ as the prior.

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-07-02 | Initial pivot plan (Claude). North-star swap wealth → PM; two new engines (daily stats + Black–Litterman belief loop) over the existing five planes; 5-slice sequence pv0–pv4; ties the build to closing review debt C1/M1/M2/M3/M4. Grounded against shipped `run_mv_rebalance` (po0), `assumptions_for`, `evaluate_risk`, IPS monitor, frozen registry, and the `MarketPriceRow` single-mark caveat. |
| 2026-07-02 | **Three open decisions resolved + FIIJ grounded (Claude).** Recs: (1) quarantine wealth machinery, (2) Black–Litterman fed by FIIJ finance-view signals, (3) thin `Book` alias. Inspected [The-FIIJ](https://github.com/hcarstens/The-FIIJ): `finance_view_history.json` is a daily z-score-valued directional-signal series with `regime_class` + Brier calibration (`oos/`, `calibrated_thresholds.json`); it *is* the signal pipeline, so views are `signal`-sourced from pv2, regime read comes free, and calibration (F8) has a ready history. pv2 reframed from generic price-history ingest to a FIIJ adapter. |
