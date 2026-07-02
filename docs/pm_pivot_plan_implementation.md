# PM Pivot — Implementation Plan

**Status:** proposed — **pv0–pv4 planned** (no slice shipped). Critical path
**pv0 → pv1**; pv1 ships the Bayesian belief loop reusing the po0 QP with **no
new market data**.
**Date:** 2026-07-02
**Owner:** decision plane (belief engine) + research plane (daily stats); all
five planes touched
**Inputs:**
[`pm_pivot_plan.md`](research/pm_pivot_plan.md) (north-star reframe — the strategic doc this steps out),
[`heuristics/Mental Model of The Portfolio Manager.md`](heuristics/Mental%20Model%20of%20The%20Portfolio%20Manager.md) (ℍ_Allocation — **north-star lens**: axioms 1–7 + "Apply by…" checklist; ¬PS2/¬RM4/¬Opt3 negations),
[`heuristics/Persona of The Portfolio Manager.md`](heuristics/Persona%20of%20The%20Portfolio%20Manager.md) (judgment companion — apply on the judgment slices pv1/pv3/pv5, not the reframe),
[`portfolio_optimization_implementation.md`](portfolio_optimization_implementation.md) (po0 `run_mv_rebalance` — the QP the posterior μ feeds; §A Σ/μ build spec),
[`portfolio_manager_implementation.md`](portfolio_manager_implementation.md) (pm0–pm2 — `pm.advise` coordinator, `AdviceBundle`, the 7-axiom narrative + `not_computed` honesty rule),
[`code_review_claude_2026-06-30.md`](code_review_claude_2026-06-30.md) (C1 red mypy; M1/M2 frozen debt; M3 dead walk-forward guards; M4 dashboard-as-orchestrator),
[`heuristics/Portfolio Optimization.md`](heuristics/Portfolio%20Optimization.md) (PO6 μ estimation error; PO7 non-stationarity),
[`messaging_protocol.md`](messaging_protocol.md) (§5 catalog, S1 atomic-op rule),
[`dev_contract_registry.md`](dev_contract_registry.md) (new `pm_pivot` track)

---

## 1. Principle — a closed daily loop: observe → update → allocate → check → report

The pivot builds the traditional PM loop as a chain of **pure, advisory** steps
over the existing planes. Nothing auto-trades (persona axiom 6). The loop's two
new engines are the *only* net-new computation; everything else is reuse.

```text
DATA                RESEARCH                    DECISION                       EXECUTION/REPORTING
price history ──► daily stats engine ──► belief engine (Black–Litterman) ──► optimizer QP ──► mandate/limit
(as_of series)    stats.daily            beliefs.update                       optimizer.propose   monitor (reuse
                  → returns, vol,        prior μ ⊕ views → posterior μ         (run_mv_rebalance,   IPS drift) →
                  corr, z-score moves,   → BeliefUpdate (frozen journal)      po0, unchanged)      alert queue →
                  P&L attribution                                             w*/Δw on posterior   Belief Journal
                        │                        │                                  │             report (F8
                        └── evidence ────────────┘                                  │             calibration)
                                                                                    └── human approval gate (unchanged)
```

**Reuse-first (S1 discipline).** The optimizer is **not** touched: `run_mv_rebalance`
already takes μ/Σ; pv1 swaps the static `class_expected_return` prior for a
**posterior** μ from the belief engine — a caller change, not an engine change.
The mandate/limit monitor **is** the shipped IPS monitor (`policy.check`) read
through PM vocabulary. Three new atomic ops are justified: `beliefs.update`
(decision plane, the BL blend), `stats.daily` (research plane, portfolio-side
statistics), and `ingest.fiij` (data plane, the FIIJ finance-view adapter); each
is a genuine new computation or ingest, not indirection over an existing op.

---

## 2. The honesty rule — computable vs `not_computed`

Every quantity the loop cannot yet compute is `not_computed` in the record and
on the dashboard, never faked (the pm/po house rule; the Goodhart guard).

| # | Quantity | Computed from | Status |
| --- | --- | --- | --- |
| 1 | **Posterior μ** (Black–Litterman blend) | prior μ (`assumptions_for("base").class_expected_return`) ⊕ views ⊕ Σ | **pv1 — computable** |
| 2 | **Target w\*/Δw on posterior μ** | `run_mv_rebalance(posterior_μ, Σ, bounds)` (po0, unchanged) | **pv1 — computable** |
| 3 | **BeliefUpdate replay record** | `(prior_id, view_set, posterior_id, method, config_version)` | **pv1 — computable** |
| 4 | **Daily return / EWMA vol / rolling corr** | price-history series (pv2 ingest) | **pv2 — computable** |
| 5 | **Move significance** (z-score vs conditional dist) | daily returns + EWMA vol | **pv2 — computable** |
| 6 | **P&L attribution** (position / factor) | returns × positions | **pv2 — computable (position); factor partial)** |
| 7 | **Signal-driven views** (FIIJ finance-view → BL view) | FIIJ `finance_view_history.json` `sheets[].signals[].value` (z-score) → sleeve tilt | **pv2 — computable** (FIIJ adapter; §11) |
| 8 | **Forecast calibration** (were the views right?) | FIIJ `oos/` Brier scorecards + `calibrated_thresholds.json`; own journal accrues too | **pv2 — ingested from FIIJ; own-journal score at pv3** |
| 9 | **Own automated signal / alpha model** | warehouse does not run a screen — it *ingests* FIIJ | **`not_computed` by design** (external source; we never fabricate alpha — §2 note) |
| 10 | **Reverse-optimization equilibrium prior** | market-cap weights → implied μ | **`not_computed`** (v0 prior = ex-ante class assumption, labelled) |
| 11 | **Regime-conditional posterior** (crisis Σ) | FIIJ `regime_class` selects base vs `high_risk` (po2) Σ in the BL blend | **pv3 — computable** (regime read supplied by FIIJ) |

**Stated limitations (surfaced, not hidden):**
- **Prior is an ex-ante class assumption**, not a reverse-optimized equilibrium
  — labelled on the panel; equilibrium prior is a documented upgrade (#10).
- **Views are `manual`/demo only in pv1** (before the FIIJ adapter lands in
  pv2); from pv2 they are `signal`-sourced from FIIJ with FIIJ-supplied
  confidence. We never fabricate our own alpha (#9) — a FIIJ signal with failing
  OOS Brier is ingested as a *low-confidence* view, never upgraded. The QP's box
  constraints remain the diversification defense (PO6); a single view does not
  license concentration.
- **Base-regime Σ** in the blend (¬PS2 / PO7) until pv3, when FIIJ's
  `regime_class` selects base vs `high_risk` (po2) Σ; the po2 stress overlay
  already runs on the *weights*, so survival (persona axiom 4) stays scored.

---

## 3. New core types (frozen + registered — builds M1/M2 right from day one)

All belief records are audit/replay-critical → `frozen=True` + appended to
`FROZEN_TYPES` in the same slice that introduces them (the review M1/M2 fix, done
correctly rather than retrofitted).

```python
# warehouse/decision/beliefs/models.py

class ViewSource(StrEnum):
    MANUAL = "manual"          # discretionary / demo — pv1 only
    FIIJ = "fiij"              # ingested FIIJ finance-view signal — pv2+
    STAT_MOVE = "stat_move"    # z-score evidence from our own stats.daily (pv3)

class View(BaseModel):                     # frozen + registered
    model_config = ConfigDict(frozen=True)
    sleeve: IpsSleeve                       # the asset the view is about
    expected_excess: Decimal                # view on excess return vs prior
    confidence: Decimal                     # [0,1] — BL Ω diagonal source
    source: ViewSource
    source_ref: str | None = None           # e.g. FIIJ signal id "CF-1" / as_of
    calibration: str = "not_computed"       # FIIJ OOS Brier when source == fiij (#8)
    rationale: str

class PriorBelief(BaseModel):              # frozen + registered
    model_config = ConfigDict(frozen=True)
    mu: dict[IpsSleeve, Decimal]            # v0 = class_expected_return (ex-ante)
    prior_source: str                       # "class_assumption" (labelled, not "equilibrium")
    assumptions_version: str                # pins the risk-plane prior

class PosteriorBelief(BaseModel):          # frozen + registered
    model_config = ConfigDict(frozen=True)
    mu: dict[IpsSleeve, Decimal]            # BL-blended posterior μ
    method: str = "black_litterman"
    tau: Decimal                            # BL scalar (pinned)

class BeliefUpdate(BaseModel):             # frozen + registered — the JOURNAL entry / replay fingerprint
    model_config = ConfigDict(frozen=True)
    correlation_id: str
    as_of_date: date
    prior: PriorBelief
    views: tuple[View, ...]                 # tuple, not list — hashable, immutable
    posterior: PosteriorBelief
    belief_config_version: str              # pins τ, Ω convention (audit replay)
    calibration: str = "not_computed"       # flips to a score once the journal has history (#8)
```

```python
# warehouse/research/stats/models.py

class DailyMove(BaseModel):                # frozen + registered
    model_config = ConfigDict(frozen=True)
    security_id: str
    as_of_date: date
    ret: Decimal                            # daily return
    ewma_vol: Decimal
    zscore: Decimal                         # move significance vs conditional dist
    significant: bool                       # |z| > pinned threshold

class DailyStatsReport(BaseModel):         # frozen + registered
    model_config = ConfigDict(frozen=True)
    as_of_date: date
    moves: tuple[DailyMove, ...]
    rolling_corr_note: str                  # correlation-shift summary (¬PS2 watch)
    attribution: tuple[PositionAttribution, ...]  # factor leg partial → not_computed rows honest
```

Every type above is appended to `FROZEN_TYPES` and asserted by
`tests/test_frozen.py` in its introducing slice — no unregistered frozen type
(the M1 anti-pattern).

---

## 4. Migration slices — PR sequence + acceptance

Package placement (no sprawl): belief engine in a new `warehouse.decision.beliefs`
(sibling to `decision.optimizer`, `decision.ips`); daily stats in a new
`warehouse.research.stats` (sibling to `research.risk`, `research.backtest`).
Both reached via one new atomic op each; both dashboards are thin loaders (M4).

### pv0 — reframe: north star + Book vocab *(docs + registry; ~1 PR)*

**Goal:** the platform *reads* as portfolio management; no engine change.

| Task | File(s) |
| --- | --- |
| Rewrite north star (wealth → PM), add PM daily-loop section | `CLAUDE.md` |
| Introduce `Book`/`Portfolio` as a thin alias over the existing working set (`PmAdvisePayload`) — additive, no `household_id` rename | `decision/pm.py`, `messaging/payloads.py` |
| Mandate/limit vocabulary: document IPS monitor (`policy.check`) as the mandate/limit monitor | `dev_contract_registry.md`, `TODO.md` |
| New `pm_pivot` track; add the missing `Persona of The Portfolio Manager` heuristics-table row | `dev_contract_registry.md`, `CLAUDE.md` |
| Catalog retheme: nav + landing copy read PM, not family office | `dashboard/pages/catalog` copy, `dashboard/navigation.py` |

**Acceptance:** `warehouse serve` catalog reads as a PM platform; `Book` alias
resolves to the shipped working set on demo + HNW rung 3; suite green; no new op.

### pv1 — Bayesian belief engine (Black–Litterman v0) *(~1 PR)*

**Goal:** `beliefs.update` returns a **posterior μ** from a prior ⊕ views, feeds
it into the existing QP, and records an immutable `BeliefUpdate` journal entry —
**with no new market data** (prior = shipped sleeve μ).

| Task | File(s) |
| --- | --- |
| `View`, `PriorBelief`, `PosteriorBelief`, `BeliefUpdate` (all frozen) | `decision/beliefs/models.py` *(new)* |
| `black_litterman(prior_mu, sigma, views, *, tau, settings) -> PosteriorBelief` — pure; the canonical `μ_BL = [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹[(τΣ)⁻¹π + PᵀΩ⁻¹Q]` blend, pure-Python linalg (no external solver, Phases 0–4) | `decision/beliefs/black_litterman.py` *(new)* |
| `update_beliefs(payload, views) -> BeliefUpdate`: prior = `assumptions_for("base").class_expected_return` (labelled `class_assumption`), Σ built via po0 §A spec | `decision/beliefs/__init__.py` *(new)* |
| New op `beliefs.update` (EVALUATE, pure) + handler | `messaging/handlers.py`, op registry |
| Feed posterior μ into `run_mv_rebalance` — **caller change only**, QP untouched | `decision/beliefs/__init__.py` |
| `belief_config_version`, `black_litterman_tau` in config (pinned) | `config.py` |
| Register all four belief types frozen | `integrity/frozen_registry.py`, `tests/test_frozen.py` |
| **Belief Journal** panel: prior μ → views (source badge `manual`) → posterior μ → resulting w\* vs pre-view w\* | `dashboard/beliefs_data.py` *(new, thin)*, `dashboard/render_beliefs.py`, `dashboard/phases.py` |

**Acceptance:**
- `beliefs.update` is pure (no `ctx.session` mutation; mirrors `test_pm_advise_pure`).
- **Zero-view identity:** empty view set → posterior μ == prior μ **byte-identical**
  → w\* == po0 baseline w\* (the PASS falsifier — no view, no move).
- **Directional:** a positive view on one sleeve raises that sleeve's posterior μ
  and its w\* (property test, no magic numbers; PO6 box caps still bind).
- **Confidence monotone:** raising a view's `confidence` moves the posterior μ
  further from prior toward the view (property test).
- `BeliefUpdate` frozen (`tests/test_frozen.py` green for all four types).
- View source renders `manual`; `calibration == "not_computed"` (honest, #8).
- `test_pm_no_new_ops` still passes for `pm.*`; `beliefs.* == {beliefs.update}`.

### pv2 — FIIJ ingest adapter + daily statistics engine *(~2 PRs)*

**Goal:** ingest FIIJ's daily finance-view as **live `signal` views**, and
compute the portfolio-side daily statistics on our own book — wiring the two
dead walk-forward guards (review M3) on the first real time series. Full FIIJ
contract in **§11 (Addendum A)**.

| Task | File(s) |
| --- | --- |
| **FIIJ adapter** `ingest_fiij_finance_view(path, as_of) -> tuple[View, ...]`: parse `finance_view_history.json`, map `sheets[].signals[].value` (z-score) → sleeve `expected_excess`, set `confidence` from FIIJ `calibrated_thresholds.json` / OOS Brier, carry `regime_class` + `source_ref` (§11) | `data/ingest/fiij.py` *(new)* |
| Price/mark **history** table `(security_id, as_of_date)` + migration; retire the single-mark `MarketPriceRow` assumption (review M3 caveat) with an `as_of_date` predicate on `list_lot_positions` | `data/ledger/models.py`, `data/ledger/views.py`, Alembic migration |
| `stats.daily(book, as_of) -> DailyStatsReport`: **our book's** returns, EWMA/realized vol, rolling corr, z-score move significance, position P&L attribution (factor leg → `not_computed`) — the portfolio-side math FIIJ does not do per-book | `research/stats/__init__.py` *(new)* |
| **Wire `assert_series_cutoff` + `assert_scenario_observations_not_after`** in both the FIIJ-ingest and stats read paths (M3 — first real series; a FIIJ snapshot dated after `as_of` must raise) | `data/ingest/fiij.py`, `research/stats/__init__.py`, `research/backtest/walk_forward.py` |
| New ops `stats.daily` + `ingest.fiij` (EVALUATE/ingest, walk-forward guarded) + handlers | `messaging/handlers.py`, op registry |
| Register `DailyMove`, `DailyStatsReport`, `PositionAttribution`, `FiijFinanceViewSnapshot` frozen | `integrity/frozen_registry.py`, `tests/test_frozen.py` |
| **Daily Movements** panel: FIIJ regime badge + significant-move table (z-scores) + vol + correlation-shift note (¬PS2); FIIJ signal→view mapping row | `dashboard/stats_data.py` *(new, thin)*, `dashboard/render_stats.py`, `dashboard/phases.py` |

**Acceptance:**
- A sample `finance_view_history.json` fixture → `ingest.fiij` yields `View`s
  with `source == "fiij"`, `expected_excess` signed like the FIIJ `value`, and a
  `confidence` traceable to a FIIJ threshold/Brier (not invented); `regime_class`
  captured on the snapshot.
- A FIIJ signal with **failing OOS Brier** ingests as a low-confidence view
  (`confidence` below the pinned floor), never upgraded (§2 / #9).
- Seeded price history → `stats.daily` returns per-security z-scores; a synthetic
  3σ move flags `significant=True`; a flat series flags none.
- **Walk-forward falsifier:** a FIIJ snapshot or price row dated *after* `as_of`
  **raises** (`WalkForwardError`) — the guard now runs (M3 closed); grep shows a
  live call site for both previously-dead guards.
- `list_lot_positions` selects the mark **at or before** `as_of` (M3 caveat fix);
  regression test pins it against a two-date history.
- Frozen types green; factor attribution rows render `not_computed`, not zero.

### pv3 — close the loop: FIIJ views → posterior → allocate → alert *(~1 PR)* — **the live proof-of-concept**

**Goal:** fuse pv1+pv2 into the daily PM loop — the biggest immediate
demonstration on live data: FIIJ's real daily file in → posterior belief →
proposed rebalance → limit alerts, on the dashboard, scored against FIIJ's own
calibration. FIIJ finance-view signals become BL views, FIIJ `regime_class`
selects the Σ regime, drift vs mandate raises an alert queue. Uses the
**sleeve rollup** (plan decision 4) so the po0 QP is reused unchanged — simplest
path that proves the whole loop end-to-end. Cross-sectional edge is recovered
later in pv5, not here.

| Task | File(s) |
| --- | --- |
| `run_pm_daily(book, as_of) -> PmDailyResult` workflow: `ingest.fiij` (views + regime) + `stats.daily` (own book) → `beliefs.update` → `run_mv_rebalance` → `policy.check` drift → alert queue | `workflows/pm_daily.py` *(new)* |
| **Regime-conditional Σ:** FIIJ `regime_class` (e.g. risk-off / crisis) selects base vs po2 `high_risk` Σ in the BL blend (#11 flips computable) | `decision/beliefs/__init__.py`, reuse `decision/optimizer/robust.py` |
| `stat_move_to_view(DailyMove) -> View` (source `stat_move`) — our own book moves as a *secondary* view alongside FIIJ (persona axiom 7 / F8) | `decision/beliefs/evidence.py` *(new)* |
| Alert queue: mandate/limit breaches surface (reuse exception-queue pattern; errors bubble) | `workflows/pm_daily.py`, dashboard exception panel |
| Belief-journal **calibration**: ingest FIIJ OOS Brier as the view calibration (#8); own realized-vs-posterior score accrues once ≥2 days of journal history | `reporting/` + `decision/beliefs` |
| **PM Daily Cockpit** panel: FIIJ regime → today's signals → posterior shift → proposed Δw → limit alerts, one screen | `dashboard/pm_daily_data.py` *(new, thin)*, `dashboard/render_pm_daily.py`, `dashboard/phases.py` |

**Acceptance:**
- `run_pm_daily` on the demo book (with a FIIJ fixture) threads one
  `correlation_id` end-to-end and returns proposed Δw driven by that day's FIIJ
  views; **stages no trade** (advisory; human gate).
- A FIIJ `regime_class` of a risk-off/crisis label routes the BL blend to the
  `high_risk` Σ; a neutral label uses base Σ (property test; #11 computable).
- A mandate/limit breach appears in the alert queue and on the cockpit panel
  (never swallowed — errors bubble).
- View `calibration` shows the FIIJ OOS Brier (not `not_computed`) when present;
  own-journal `BeliefUpdate.calibration` stays `not_computed` under 2 days of
  history, scores after (honest F8).
- `test_pm_no_new_ops`-style op-surface checks green (no coordinator op added).

### pv4 — quarantine wealth machinery + fix C1 *(~1 PR)*

**Goal:** relocate wealth-specific code to an optional module; green the gate.

| Task | File(s) |
| --- | --- |
| Move tax scenarios, wash chains, TLH, asset location, trust/beneficiary logic into `warehouse.wealth` (optional import; tests move with them) | `warehouse/wealth/*` *(new)*, moved from `decision/tax`, `data/ledger/wash_chains.py`, entity graph extras |
| Wealth dashboard panels behind a nav toggle (still wired, not deleted) | `dashboard/navigation.py`, `dashboard/phases.py` |
| **Fix C1** — malformed `# type: ignore` in `pm_workout.py:97`; **fix C2** — model the pure-leg session as `Session \| None` | `decision/pm_workout.py`, `messaging/models.py` |
| Fix review nits along the way: `ruff target-version = py312` (m5), align E501 exemptions (m4) | `pyproject.toml` |

**Acceptance:** `mypy src` clean (C1/C2 closed); wealth modules import optionally;
full suite green; `warehouse serve` shows wealth panels behind the toggle.

### pv5 — hierarchical name-selection layer (option 3) *(later — after the PoC)*

**Goal:** recover FIIJ's cross-sectional edge the sleeve rollup discards, *without*
a large-N MV optimizer. Two layers compose: the po0 QP sets **top-down** sleeve
weights (unchanged); a **within-sleeve** layer turns FIIJ per-ticker
`breakouts.csv` into name weights *inside* each sleeve's budget. Final book =
sleeve weight × within-sleeve name weights. The estimation-error blowup (PO6 /
persona ¬Opt3) is contained inside each sleeve, never a global 100×100 Σ.

| Task | File(s) |
| --- | --- |
| Ingest `breakouts.csv` → per-instrument signals with FIIJ calibration | `data/ingest/fiij.py` *(extend)* |
| `select_within_sleeve(sleeve, budget, signals) -> dict[instrument, weight]`: bounded name weights inside the sleeve budget (risk-parity / signal-tilt, **single-name cap**, not global MV) | `decision/beliefs/selection.py` *(new)* |
| Compose sleeve QP output × within-sleeve selection → instrument-level target book | `workflows/pm_daily.py` *(extend)* |
| Per-name constraints (single-name cap, optional sector cap); still advisory (no execution) | `decision/beliefs/selection.py` |
| **Name-Selection** panel: sleeve → chosen names + weights + FIIJ signal per name | `dashboard/selection_data.py` *(new, thin)*, `dashboard/render_selection.py` |

**Acceptance:** instrument-level target book whose per-sleeve sums equal the po0
sleeve weights (composition identity); single-name cap binds on a concentrated
FIIJ fixture; **no global N×N covariance is built** (test asserts selection is
per-sleeve); advisory — stages no trade. **Explicitly not** naïve instrument MV.

---

## 5. Protocol & boundary invariants — acceptance matrix

| Invariant | Source | Test |
| --- | --- | --- |
| Belief + stats engines are **pure** — no `ctx.session` mutation, no persist | messaging §4.1, persona axiom 6 | `test_beliefs_update_pure`, `test_stats_daily_pure` |
| Zero-view → posterior == prior (byte-identical) → w\* == po0 baseline | BL identity | `test_zero_view_identity` |
| Views labelled by source; `manual`/demo never dressed as a forecast | PO6, persona ¬Opt3, Goodhart | `test_view_source_labelled` |
| `BeliefUpdate` / `DailyStatsReport` frozen + registered | CLAUDE.md frozen rule (M1/M2) | `tests/test_frozen.py` |
| Both dead walk-forward guards now have a live call site | review M3 | `test_series_cutoff_wired`, grep guard |
| `list_lot_positions` picks the mark **at or before** `as_of` | review M3 caveat | `test_position_mark_cutoff` |
| Loop is **advisory** — Δw proposed, no trade staged, nothing auto-executed | human gate (CLAUDE.md) | `test_pm_daily_no_persist` |
| Mandate/limit breach surfaces (never swallowed) | errors-bubble | `test_pm_daily_alert_surfaces` |
| Calibration `not_computed` until journal has history | F8 honesty | `test_calibration_not_computed_v0` |
| `beliefs.*`/`stats.*`/`ingest.fiij` are the only new ops; `pm.* == {pm.advise}` | messaging S1 | `test_op_surface`, `test_pm_no_new_ops` |
| FIIJ view confidence traces to a FIIJ threshold/Brier — never invented; failing-OOS signal stays low-confidence | §2 #9, PO6 | `test_fiij_confidence_from_calibration`, `test_failing_brier_low_confidence` |
| FIIJ `regime_class` selects base vs crisis Σ (no silent default to base) | ¬PS2 / PO7 (#11) | `test_regime_selects_sigma` |
| τ, Ω convention, z-threshold pinned to config versions | audit replay | `test_belief_config_pinned` |
| Dashboard panels are thin loaders (engines in-plane) | Cartography/Libraries (M4) | `test_beliefs_panel_thin`, `test_stats_panel_thin` |

---

## 6. Test plan summary

| File | Covers |
| --- | --- |
| `tests/test_black_litterman.py` | BL blend correctness: zero-view identity, directional view, confidence-monotonicity, pure-Python linalg vs a hand-checked 2-sleeve case |
| `tests/test_beliefs_update.py` | prior assembly from `class_expected_return`, posterior → QP wiring, `BeliefUpdate` journal fields, view-source labelling |
| `tests/test_stats_daily.py` | returns/vol/z-score, significant-move flag, **walk-forward guard raises on future-dated series**, factor attribution `not_computed` |
| `tests/test_position_mark_cutoff.py` | M3 caveat fix — mark selected at/≤ `as_of` on a two-date history |
| `tests/test_pm_daily.py` | `run_pm_daily` end-to-end demo + HNW rung 3; advisory (no persist); alert-queue surfacing; calibration flip with history |
| `tests/test_frozen.py` | `View`, `PriorBelief`, `PosteriorBelief`, `BeliefUpdate`, `DailyMove`, `DailyStatsReport` immutable |
| `tests/test_pm_pivot_docs.py` *(optional)* | `Book` alias resolves; heuristics-table row present |

**CI gate:** BL identity + directional + confidence-monotone, stats walk-forward
raise, mark-cutoff regression, advisory no-persist, frozen registry, op-surface
unchanged, config pinned.

---

## 7. Dependencies & build order

```text
existing: run_mv_rebalance (po0), assumptions_for/class_expected_return, evaluate_risk,
          IPS monitor (policy.check), frozen registry, dashboard shell            [shipped]
  └─ pv0  reframe (docs + Book alias + mandate vocab)                             [planned]
       └─ pv1  Black–Litterman belief engine → posterior μ into the QP            [planned — critical path]
            └─ pv2  FIIJ ingest adapter + daily stats + wire M3 guards            [planned]
                 └─ pv3  close the loop (FIIJ views + regime → posterior → alert) [planned — LIVE PoC]
                      └─ pv4  quarantine wealth machinery + fix C1/C2             [planned]
                           └─ pv5  hierarchical name-selection (option 3)         [later — after PoC]

FIIJ (external, github.com/hcarstens/The-FIIJ) — the live signal source:
  finance_view_history.json (views + regime_class)  → pv2 ingest → pv3 loop
  oos/ Brier + calibrated_thresholds.json           → view confidence + calibration (#8)

Parallel (non-blocking):
  reverse-optimization equilibrium prior  → replaces the ex-ante class prior (#10)
  crisis-Σ posterior overlay (po2 Σ)      → wired in pv3 via FIIJ regime_class (#11)
```

**Depends on:** po0 QP, risk-plane Σ/μ, IPS monitor, frozen registry.
**Does not depend on:** tax estimate engine (stays `$0`/quarantined), any
external/commercial solver, Phase 5 infra, a signal/alpha pipeline (v0 views are
`manual`).

**pv1 ships the distinctive engine with zero new market data** — the prior is the
shipped sleeve μ; pv2's price history is only needed to make views *evidence-driven*
in pv3.

---

## 8. Fixture matrix (acceptance books)

| Fixture | Source | Exercises |
| --- | --- | --- |
| Demo seed | `DEMO_HOUSEHOLD_ID` (DB bootstrap) | End-to-end Belief Journal + PM Daily Cockpit |
| **FIIJ sample snapshot** | checked-in `finance_view_history.json` slice (one `as_of`) | `ingest.fiij` → `signal` views; regime badge; confidence from calibration |
| **FIIJ failing-Brier signal** | crafted snapshot + low OOS Brier | low-confidence view, never upgraded (§2 #9) |
| `general_hnw` rung 3 | `project_to_asset_portfolio` → 5-sleeve | Multi-sleeve posterior shift, interior QP on posterior μ |
| **zero-view probe** | any book, empty view set | posterior == prior, w\* == po0 baseline — the PASS falsifier |
| **3σ-move series** | crafted price history, one security spikes | `stats.daily` flags `significant`; pv3 turns it into a `stat_move` view |
| **crisis-regime snapshot** | FIIJ `regime_class` = risk-off/crisis | BL blend routes to `high_risk` Σ (#11) |
| `concentrated_stress` rung 4, seed 42 | SDG2 negation, `validate=False` | Mandate/limit breach → alert queue; posterior does not license the breach (box caps bind) |

Synthetic rungs run the in-process path (no DB) for panel loaders (mirrors
`optimizer_data.py` / `analyst_data.py`); demo uses DB bootstrap.

---

## 9. Doc updates on ship

| Doc | Update |
| --- | --- |
| [`CLAUDE.md`](../CLAUDE.md) | North star wealth → PM; PM daily-loop section; add the missing `Persona of The Portfolio Manager` heuristics-table row |
| [`pm_pivot_plan.md`](research/pm_pivot_plan.md) | Flip slice statuses as pv0–pv4 ship; cross-ref the shipped ops |
| [`dev_contract_registry.md`](dev_contract_registry.md) | New `pm_pivot` track; `warehouse.decision.beliefs` + `warehouse.research.stats` boundaries; `beliefs.update` / `stats.daily` ops |
| [`../TODO.md`](../TODO.md) | pv0–pv4 rows; wealth-machinery quarantine; C1/C2 fix |
| [`../JOURNAL.md`](../JOURNAL.md) | Per-slice build log |
| [`code_review_claude_2026-06-30.md`](code_review_claude_2026-06-30.md) | Note C1/C2/M1/M2/M3 closure as the pivot lands |

---

## 10. Self-review

### Strengths
- **Distinctive engine shippable first, no new data** — pv1 delivers the
  Bayesian loop on the shipped sleeve μ prior + the po0 QP; the optimizer is a
  caller change, not an engine change (S1 minimal surface).
- **FIIJ collapses two risks at once** — it is the external signal pipeline *and*
  a ready-made calibration history, so views are `signal`-sourced (not manual)
  and the loop is scorable (F8) from pv2, plus `regime_class` closes the ¬PS2 Σ
  gap in pv3 for free. The warehouse ingests, never fabricates, alpha (#9).
- **Pays down review debt as it builds** — belief/stats records are frozen +
  registered from day one (M1/M2); pv2 wires the two dead guards (M3) on the
  first real time series and fixes the mark-cutoff caveat; engines live in-plane
  (M4); pv4 fixes the red gate (C1/C2).
- **Honest by construction** — views `manual`, calibration `not_computed`,
  factor attribution `not_computed` until real; nothing faked (Goodhart guard).
- **Persona-native** — the loop *is* axiom 7 (rebalance on calibrated evidence);
  box caps hold ¬Opt3/PO6 against demo-view concentration; po2 crisis-Σ still
  scores survival (axiom 4).
- **Advisory/acting split preserved** — every new step is pure; the human gate
  is untouched.

### Risks & mitigations
| Risk | Mitigation |
| --- | --- |
| BL linalg (matrix inverse) in pure Python | Restrict to the 6-sleeve class block (small, well-conditioned); hand-checked 2-sleeve regression; raise on singular Σ (no silent pinv) |
| Demo/FIIJ views drive spurious rebalances | Zero-view identity test; box caps bind; view source labelled; FIIJ confidence traces to OOS Brier (failing-Brier → low confidence, never upgraded) |
| FIIJ signal→sleeve enum drift silently mis-maps | Explicit total `FiijMappingError`-raising map (mirrors po0 §A.1); regression test |
| Price-history migration reopens M3 join hazard | Wire `assert_series_cutoff` + `as_of` predicate *before* any stats read; `test_position_mark_cutoff` regression |
| `household_id` → `Book` rename churn | Thin alias in pv0, not a global rename (pm_pivot_plan open decision 3) |
| Wealth quarantine breaks tests | pv4 moves modules with their tests; suite green is the acceptance gate |
| Calibration read as real before history exists | `calibration` stays `not_computed` under 2 days; test pins the v0 state |

### Verdict
**Ready to execute** starting with pv0 (reframe) → pv1 (Black–Litterman belief
engine). **pv3 is the live proof-of-concept** — FIIJ's real daily file driving a
posterior + rebalance on the dashboard — reached via the sleeve rollup so the
po0 QP is reused unchanged (plan decision 4). Critical path pv0 → pv1 → pv2 →
pv3; pv4 is cleanup/gate-fix; **pv5 (hierarchical name selection, option 3)
comes after the PoC** and recovers FIIJ's cross-sectional edge without a
large-N MV optimizer. The pivot closes review findings C1, C2, M1, M2, and M3 as
a side effect of building the loop correctly.

---

## 11. Addendum A — FIIJ ingest contract (pv2 spec)

The first live views come from [The-FIIJ](https://github.com/hcarstens/The-FIIJ),
a daily 30-day forecast engine over equities / commodity ETFs / crypto. FIIJ
already performs the *daily-statistics → scored directional signal* transform, so
the warehouse **ingests** its output rather than re-deriving it. This is the
authoritative pv2 adapter spec.

### A.1 Source artifacts (read-only; FIIJ owns them)

| FIIJ file | Shape | Warehouse use |
| --- | --- | --- |
| `data/finance_view_history.json` | list of daily snapshots: `as_of_date`, `fetched_at`, `regime_label`, `regime_class`, `pending_signals`, `sheets[]` where each sheet has `vote`, `dominant_direction`, `signals[]` = `{id, name, value ∈ ~[-1,1], available, detail}` | primary view feed + regime read |
| `data/calibrated_thresholds.json` | `{thresholds{...}, updated_at, sample_size}` | confidence floor / mapping for `View.confidence` |
| `oos/STATS.md`, `oos/backtest_summary.json`, `oos/*_trades.csv` | OOS Brier calibration + realized trades per strategy | view `calibration` (#8), realized-vs-forecast ground truth |
| `data/breakouts.csv` | per-ticker breakout signals (instrument level) | *deferred to pv2b* — instrument-level views rolled to sleeves |
| `data/equity_curve.csv` | realized paper-trading equity curve (Alpaca equity) | attribution / calibration cross-check |

### A.2 Mapping `signal.value` → `View`

FIIJ `signal.value` is a **signed, z-score-derived directional score** (the
`detail` field carries the raw `z=` components). The adapter:

1. **Selects the snapshot** for the requested `as_of` (walk-forward: raise if the
   only available snapshot is dated *after* `as_of` — M3 guard).
2. **Maps each active sheet/signal to a sleeve** via an explicit, total,
   **raising** map (same discipline as po0's `_SLEEVE_TO_RISK`, §A.1 there): FIIJ
   macro sheets (Cash Flow / FX / rates …) and strategy tags (`silk_equity`,
   `silk_commodity_etf`, `silk_crypto`) → `IpsSleeve`. An unmapped FIIJ signal
   **raises `FiijMappingError`**, never a silent drop.
3. **Sets `expected_excess`** = a pinned scale factor × `signal.value` (the scale
   is version-pinned in `fiij_config_version`; the value is a *tilt vs prior*, not
   an absolute μ — labelled).
4. **Sets `confidence`** from FIIJ calibration: a signal whose strategy's OOS
   Brier passes maps to a higher Ω-confidence; a **failing-Brier** strategy (FIIJ
   itself only runs `silk_equity` live for this reason) maps **below the pinned
   confidence floor** — ingested, never upgraded (§2 #9).
5. **Carries** `source = fiij`, `source_ref = "{signal.id}@{as_of}"`,
   `calibration` = the FIIJ OOS Brier string, and the snapshot's `regime_class`
   onto a frozen `FiijFinanceViewSnapshot` record.

```python
class FiijFinanceViewSnapshot(BaseModel):   # frozen + registered
    model_config = ConfigDict(frozen=True)
    as_of_date: date
    fetched_at: datetime
    regime_class: str                        # → base vs high_risk Σ (pv3, #11)
    views: tuple[View, ...]                  # source == fiij
    fiij_config_version: str                 # pins the value→excess scale + Brier map
```

### A.3 Boundaries and honesty

- **Read-only, one-way.** The warehouse never writes back to FIIJ; the adapter is
  an ingest boundary. FIIJ's launchd cadence (pre-market daily) is upstream; the
  warehouse reads whatever snapshot is ≤ `as_of`.
- **No fabricated alpha.** Every `View` is traceable to a FIIJ `signal.id`; the
  adapter invents no view FIIJ did not emit, and never raises a confidence FIIJ's
  calibration does not support (PO6 / persona ¬Opt3).
- **Regime, not just signals.** `regime_class` is a *free* regime read that pv3
  uses to pick base vs crisis Σ (#11) — the one place FIIJ closes the ¬PS2 gap
  the warehouse would otherwise defer.
- **Sleeve-level v0 — the deliberate proof-of-concept altitude.** Macro-sheet
  and strategy-tag signals net to a tilt per 6-sleeve; this reuses the po0 QP
  unchanged and is the simplest thing that proves the whole live loop
  end-to-end. It **discards FIIJ's cross-sectional (name-picking) edge** — long
  NVDA / short MSFT nets to ~neutral "equity" — which the Daily Movements /
  Belief Journal panels **must state on-screen** ("sleeve-level; name dispersion
  not expressed"), never imply the book acts on individual FIIJ names. Recovering
  that edge is **pv5** (hierarchical layer, §5), *not* naïve N×N instrument MV
  (rejected — PO6 / ¬Opt3 estimation-error trap). Per-ticker `breakouts.csv`
  ingestion is the pv5 input, deferred with this slice.
- **Transport.** v0 reads a checked-in / path-configured FIIJ export
  (`fiij_export_path` in config); a live pull (git submodule / HTTP) is a pv2b
  concern. The adapter is agnostic to transport — it takes a path.

### A.4 Deltas folded into §2–§8

- Honesty matrix #7/#8/#9/#11 updated (FIIJ supplies signals, calibration, regime).
- pv2 gains `ingest.fiij` op + `data/ingest/fiij.py` + `FiijFinanceViewSnapshot`
  frozen type; pv3 consumes `regime_class` for Σ selection.
- Invariants matrix adds `test_fiij_confidence_from_calibration`,
  `test_failing_brier_low_confidence`, `test_regime_selects_sigma`; a
  `FiijMappingError` raise test mirrors po0's `test_sleeve_mapping_raises`.

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-07-02 | Initial stepped plan (Claude). Steps out [`pm_pivot_plan.md`](research/pm_pivot_plan.md) into pv0–pv4: reframe → Black–Litterman belief engine (posterior μ into the po0 QP, no new data) → daily stats + price history + M3 guard wiring → close the loop → quarantine wealth + fix C1/C2. Frozen belief/stats records (M1/M2), in-plane engines (M4), advisory-only (human gate). Two new ops justified (`beliefs.update`, `stats.daily`); QP/IPS-monitor reused unchanged. Grounded against shipped `run_mv_rebalance`, `assumptions_for`, `evaluate_risk`, IPS `policy.check`, the frozen registry, and the `MarketPriceRow` single-mark caveat. |
| 2026-07-02 | **FIIJ grounded + decisions resolved (Claude).** Inspected [The-FIIJ](https://github.com/hcarstens/The-FIIJ): `finance_view_history.json` = daily snapshots with z-score-valued `sheets[].signals[]`, `regime_class`, `pending_signals`; `calibrated_thresholds.json` + `oos/` Brier = calibration; `equity_curve.csv` = realized. Reframed pv2 from generic price-history ingest to a **FIIJ adapter** (§11): views become `source=fiij` (not `manual`), confidence traces to FIIJ Brier (failing-Brier → low confidence, never upgraded), and `regime_class` selects base vs crisis Σ in pv3 (#11 → computable). Added third op `ingest.fiij`, `FiijFinanceViewSnapshot` frozen type, FIIJ fixtures + invariants, and Addendum A (ingest contract). Honesty #7/#8/#9/#11 updated. |
| 2026-07-02 | **Granularity decided: sleeve rollup for the live PoC, hierarchical later (Claude).** Plan decision 4: v0 rolls FIIJ signals up to the 6 sleeves so the po0 QP is reused unchanged — the simplest/biggest immediate proof of a live concept (pv3). Panels must disclose the discarded cross-sectional edge. Added **pv5** (option 3: top-down sleeve QP × within-sleeve FIIJ name selection, single-name caps, no global N×N Σ) as the post-PoC deepening. Naïve instrument-level MV explicitly rejected (PO6 / ¬Opt3). |
