# Portfolio Manager — Implementation Plan

**Status:** pm0–pm2 **shipped** (narrative + axiom checklist, rebalance advisory workflow, dashboard panel; tax leg stays an intentional $0 stub — see §next)
**Date:** 2026-06-28
**Owner:** decision plane / orchestrator
**Inputs:** [`heuristics/Mental Model of The Portfolio Manager.md`](heuristics/Mental%20Model%20of%20The%20Portfolio%20Manager.md) (ℍ_Allocation — north star),
[`messaging_protocol.md`](messaging_protocol.md) (§4.1 coordinator, §5 catalog, §6 PM lens),
[`research/hnw_portfolios.md`](research/hnw_portfolios.md) (graph axiom, cohorts, rung ladder),
[`heuristics/Mental Model of The Portfolio Analyst.md`](heuristics/Mental%20Model%20of%20The%20Portfolio%20Analyst.md) (Goodhart vigilance),
[`heuristics/Mental Model of The Tax Analyst.md`](heuristics/Mental%20Model%20of%20The%20Tax%20Analyst.md),
[`messaging_protocol_implementation.md`](messaging_protocol_implementation.md) (m1 shipped baseline),
[`dev_contract_registry.md`](dev_contract_registry.md),
[`portfolio_analyst_implementation.md`](portfolio_analyst_implementation.md) (pa0–pa2 shipped),
[`portfolio_optimization_implementation.md`](portfolio_optimization_implementation.md) (po0+ next),
[`research/portfolio_optimization.md`](research/portfolio_optimization.md),
[`heuristics/Portfolio Optimization.md`](heuristics/Portfolio%20Optimization.md) (PO1–PO8)

---

## 1. Principle — advisory in, acting out

The Portfolio Manager is the **allocation-and-survival coordinator**: it judges the *whole book*,
fans out to specialists, and returns a single advisory artifact. It **never mutates** — that
boundary is the messaging protocol's `COMMAND` kind and the PM axiom *control exposure, not
outcomes*.

| Layer | Package / `op` | Role | Kind |
| --- | --- | --- | --- |
| **Orchestrator** | `workflows/*`, CLI | `QUERY` + `COMMAND` chain; owns `correlation_id` | mixed |
| **Portfolio Manager** | `decision.pm` → `pm.advise` | Coordinate specialists; score the 7-axiom diagnostic | EVALUATE composite |
| **Risk** | `research.risk` → `risk.evaluate` | Whole-book risk report (policy-agnostic) | EVALUATE |
| **Portfolio Analyst** | `decision.ips` → `policy.check` | IPS drift, concentration | EVALUATE |
| **Portfolio Optimization** | `decision.optimizer` → `optimizer.propose` | TLH + greedy rebalance proposal | EVALUATE |
| **Tax Analyst** | `decision.tax` → `tax.scenario` | After-tax baseline vs overlay delta | EVALUATE |

```text
ORCHESTRATOR                          PORTFOLIO MANAGER (pure composite)
ledger.positions ──► working set ──► pm.advise ──┬── risk.evaluate           (whole book, no IPS)
(P, IPS) manifest                                ├── policy.check            (Portfolio Analyst — drift)
                                                 ├── attribution.evaluate    (Portfolio Analyst — pa0+)
                                                 ├── optimizer.propose       (Optimization)
                                                 └── tax.scenario            (Tax Analyst — stub)
        │                                          → score_pm_axioms → PmNarrative
        └──► optimizer.persist → approval.* → orders.stage   (COMMAND — outside PM)
```

**Messaging contract (§4.1, §5):** no new atomic `op`s, and **no port/adapter layer** — the
registry *is* the indirection; `pm.advise` already nest-dispatches the specialist ops (shipped in
m1). PM v0 adds exactly two things on top: **working-set assembly** and the **7-axiom narrative**.
Upgrading a specialist = improve the function behind its `op`, not add an abstraction. (Same
reason `portfolio.analyst` was rejected — `policy.check` is the atomic op, S1.)

**HNW context:** the working set is a **household-scoped graph artifact** (lot-level positions +
IPS + projected manifest), not a weight vector alone (`hnw_portfolios.md` graph axiom). v0 uses
the demo household + synthetic cohort fixtures; rung 3/4 books exercise concentration, liquidity
tiers, and lot granularity.

---

## 2. Scope — what ships vs deferred

### In scope (pm0–pm2)

| Item | Rationale |
| --- | --- |
| `score_pm_axioms(bundle, payload) → PmNarrative` in `decision/pm.py` | The PM value-add — the 7-axiom diagnostic |
| One honest `specialist_status` map (tax `stub`; risk/analyst/optimizer `live`) | Dashboard never implies real tax numbers |
| `build_working_set(session, household_id)` → `PmAdvisePayload` | Assembly step; reuses `lot_positions_from_fixture` for HNW |
| `run_rebalance_advisory` workflow — `ledger.positions` → `pm.advise` | First orchestrator client beyond daily_refresh |
| Freeze + register `AdviceBundle` and `PmNarrative` | Advisory snapshots are audit/replay-critical |
| Dashboard: advisory panel — axiom strip + specialist badges | Dashboard-first |
| Falsifier tests + `portfolio_manager` track in registry | Contract discipline |
| HNW smoke: demo household + `emit_synthetic_household` rung 3 | Whole-book path on graph-coherent fixture |

### Deferred

| Item | Why |
| --- | --- |
| PM that **persists** (would be `COMMAND`) | Advisory-only v0; orchestrator owns `optimizer.persist` |
| PM axiom scoring of analyst attribution / kill / NPA | Legs shipped (pa0–pa2); `score_pm_axioms` enrichment deferred — Addendum C |
| Threshold-aware tax estimate (NIIT/AMT cliffs) | `evaluate_tax_scenario` returns zeros today; `TODO.md` tax-estimate track |
| Axiom 5 (margin of safety) real scoring | No valuation engine — marked `not_computed`, not faked (§4) |
| Axiom 3/6/7 enrichment from analyst + po0 | v0 scores drift/concentration/binding-count only; see Addendum C |
| Axiom 7 turnover-cost awareness | Deferred to po1 `‖Δw‖₁` reporting (PO8) |
| Axiom 4 crisis-correlation stress | Deferred to po2 scenario-robust Σ (PO7) |
| Mean-variance QP / risk-budget optimizer | `portfolio_optimization.md` — heuristic v0 ships; MIP path exists |
| Autonomous rebalance (skip approval) | Human gates dominate |
| LLM narrative / IPS prose interpreter | Open question in `TODO.md` |

---

## 3. Specialist legs — liveness map (no ports)

Specialists are reached **only via `dispatch_message`** to their registered `op` (the m1 fan-out).
There is **no `AnalystPort`/`OptimizerPort`/`TaxPort` layer** — that would be a second indirection
over the registry the protocol already provides (S1/S2). Enrichment replaces the **backing
function** behind the `op`; the `op` and `AdviceBundle` shape are stable.

| Leg | `op` | Backing | Status | Feeds PM axioms |
| --- | --- | --- | --- | --- |
| **Risk** | `risk.evaluate` | `evaluate_risk` | **live** | 1 (whole book), 2 (variance contributions), 4 (stress/ES) |
| **Portfolio Analyst** | `policy.check` | `build_ips_drift_report_from_views` | **live** (drift + `concentration_alerts`) | 3 (concentration), 7 (drift vs target) |
| **Portfolio Analyst** | `attribution.evaluate` | `evaluate_attribution` | **live** (pa0–pa2) | *(enrichment pending — Addendum C)*; feeds axiom 1/3 when wired |
| **Optimization** | `optimizer.propose` | `run_tax_aware_optimizer` | **live** (TLH + greedy) | 6 (binding constraints) |
| **Tax Analyst** | `tax.scenario` | `evaluate_tax_scenario` → **zeros** | **stub** | *(no PM axiom)* — feeds optimization objective hierarchy when live; see Addendum A.1 |

Only the **tax** leg is a genuine stub (confirmed: `evaluate_tax_scenario` returns zeros pending
the estimate engine). Risk, analyst, and optimizer are live — do **not** wrap them in stub
envelopes; surface their liveness once, in `PmNarrative.specialist_status`.

---

## 4. PM core types

No new `PortfolioWorkingSet` type — the working set **is** `PmAdvisePayload` (already shipped:
`household_id, positions, ips, manifest, request, tax_overlays`). Add optional provenance fields
to it rather than forking a near-duplicate.

```python
class PmAdvisePayload(BaseModel):       # extend the existing payload (additive)
    household_id: str
    positions: list[LotPositionView]
    ips: InvestmentPolicyStatement
    manifest: AssetPortfolio
    request: RiskRequest
    tax_overlays: TaxScenarioOverlays = TaxScenarioOverlays()
    cohort_id: str | None = None        # + from synthetic provenance when present
    as_of_date: date | None = None      # +

class AxiomScore(StrEnum):
    PASS = "pass"            # measured, within tolerance
    WARN = "warn"            # measured, near a limit
    BREACH = "breach"        # measured, out of band
    NOT_COMPUTED = "not_computed"   # no input produces this yet — NOT a silent pass

class PmNarrative(BaseModel):           # frozen + registered (audit snapshot)
    model_config = ConfigDict(frozen=True)
    correlation_id: str
    axioms_scored: dict[str, AxiomScore]   # axiom_id → score (honest about gaps)
    headline: str
    specialist_status: dict[str, str]      # risk|analyst|optimizer|tax → live|stub

class AdviceBundle(BaseModel):          # frozen + registered in pm0 (was unfrozen)
    model_config = ConfigDict(frozen=True)
    risk: RiskResult
    proposal: OptimizationResult
    tax: TaxScenarioResult
    drift: IpsDriftReport
    attribution: AttributionReport | None = None   # additive — pa0 5th leg
    narrative: PmNarrative | None = None   # additive — consumers default to None
```

**Axiom computability (the honesty rule).** The 7-axiom diagnostic is the PM's real output, and
~6/7 are computable from existing leg outputs today. The narrative must mark the genuine gap as
`not_computed`, never a fabricated `pass` — exactly the **Goodhart trap the Portfolio Analyst
model's own axiom 6 warns against** (a score that looks like measurement but isn't).

| PM axiom | Computed from | pm0 |
| --- | --- | --- |
| 1 portfolio is the unit of account | `risk.evaluate` over the whole manifest | scorable |
| 2 effective (corr-adjusted) bets | `RiskResult` level-2 variance contributions → inverse-HHI | scorable |
| 3 position sizing / concentration | `policy.check` `concentration_alerts` | scorable |
| 4 survive to compound | risk Level-4 stress / ES worst case | scorable (partial — linear sleeve replay; no correlation-regime shock; see Addendum A.2) |
| **5 margin of safety (component)** | **— no valuation engine** | **`not_computed`** |
| 6 control exposure, not outcomes | `optimizer.propose` `binding_constraints` | scorable |
| 7 rebalance on calibrated evidence | `policy.check` drift vs target | scorable |

---

## 5. Migration slices — PR sequence + acceptance

Acceptance is **downstream behavior**: a workflow runs `pm.advise` on a whole book; the dashboard
shows the axiom strip + an honest tax-stub badge; the advisory smoke passes on demo + HNW rung 3.
No 6-file package — PM logic is a single `decision/pm.py` (the `_pm_advise` handler stays the thin
composition root in `handlers.py` and calls into it).

### pm0 — narrative + axiom checklist *(~1 PR)*

**Goal:** `pm.advise` returns a scored 7-axiom diagnostic, not just four raw legs.

| Task | File(s) |
| --- | --- |
| `PmNarrative`, `AxiomScore`; freeze `AdviceBundle` | `messaging/payloads.py` (or `decision/pm.py`) |
| `score_pm_axioms(bundle, payload) -> PmNarrative` (table §4 mapping; axiom 5 → `not_computed`) | `decision/pm.py` *(new)* |
| `specialist_status` = `{risk: live, analyst: live, optimizer: live, tax: stub}` | `decision/pm.py` |
| `_pm_advise` calls `score_pm_axioms`, attaches `narrative` | `messaging/handlers.py` |
| Add `cohort_id` / `as_of_date` to `PmAdvisePayload` | `messaging/payloads.py` |
| Register `AdviceBundle`, `PmNarrative` frozen | `integrity/frozen_registry.py`, `tests/test_frozen.py` |

**Acceptance:**

- `dispatch_message(pm.advise)` still pure (poisoned-session coordinator test green — unchanged).
- `narrative.specialist_status["tax"] == "stub"`; the other three `== "live"`.
- `narrative.axioms_scored["axiom_5"] == "not_computed"`; ≥6/7 others are `pass`/`warn`/`breach`.
- `pytest tests/test_frozen.py` green (`AdviceBundle`, `PmNarrative`).

### pm1 — working set + rebalance advisory workflow *(~1 PR)*

**Goal:** first orchestrator beyond `daily_refresh` — the advisory half of the rebalance loop.

| Task | File(s) |
| --- | --- |
| `build_working_set(session, household_id) -> PmAdvisePayload` (positions + IPS + projected manifest) | `decision/pm.py` |
| HNW path **reuses `lot_positions_from_fixture`** (`synthetic/fixture_views.py`) — no reinvented projection | `decision/pm.py` |
| `run_rebalance_advisory(session, household_id, *, correlation_id)` — chain `ledger.positions` → `build_working_set` → `pm.advise` | `workflows/rebalance_advisory.py` *(new)* |
| HNW smoke: `emit_synthetic_household(cohort="general_hnw", rung=3)` → fixture → `pm.advise` | `tests/test_pm_workflow.py` *(new)* |
| Register workflow in `workflows/catalog.py` | `workflows/catalog.py` |

**Acceptance:**

- Demo household: `run_rebalance_advisory` returns `AdviceBundle` with shared `correlation_id`.
- HNW rung 3 fixture (in-process, via `lot_positions_from_fixture`): same path, no exception;
  concentration alert present in `drift`.
- **Does not** call `optimizer.persist` or approval ops (advisory only).

### pm2 — dashboard + registry *(~1 PR)*

**Goal:** living PM status on the dashboard; track registered.

| Task | File(s) |
| --- | --- |
| Advisory panel — axiom strip (incl. `not_computed` rendered honestly) + specialist badges (tax = `stub`) | `dashboard/render_advisory.py`, `advisory_data.py` |
| `portfolio_manager` track + boundary row `warehouse.decision.pm` | `dev_contract_registry.md` |
| TODO rows for pm track + tax-stub → live upgrade | `TODO.md` |

**Acceptance:**

- `warehouse serve` shows the PM narrative, the axiom checklist, and a visible `tax: stub` badge.
- Falsifiers green (§6).

---

## 6. Protocol invariants — acceptance matrix

| Invariant | Source | Test |
| --- | --- | --- |
| PM never reads `ctx.session` for mutation | messaging §4.1, PM axiom 6 | `test_pm_advise_pure` (existing) |
| Whole book — full positions + manifest passed to risk | PM axiom 1, hnw graph axiom | `test_pm_workflow_hnw_rung3` |
| No new `op`s; specialists reached via dispatch only | messaging §5 S1 | `test_pm_no_new_ops` |
| Tax leg explicitly `stub` until estimate ships | Tax Analyst ¬Opt3 deferred | `test_tax_scenario_stub_zero` |
| Analyst leg **live** (drift + concentration), attribution deferred | Portfolio Analyst scope | `test_policy_check_concentration_live` |
| Axiom 5 scored `not_computed`, never faked `pass` | Goodhart (Analyst axiom 6) | `test_axiom5_not_computed` |
| `correlation_id` threads through advisory workflow | messaging §4.1 | `test_rebalance_advisory_correlation` |
| COMMAND chain outside PM | messaging §6 | rebalance smoke does not persist |

---

## 7. Test plan summary

| File | Covers |
| --- | --- |
| `tests/test_messaging_coordinator.py` | *(existing)* pm.advise purity + rebalance loop |
| `tests/test_pm_narrative.py` | axiom scoring, `not_computed` honesty, specialist_status |
| `tests/test_pm_workflow.py` | `run_rebalance_advisory` demo + HNW rung 3 |
| `tests/test_dashboard.py` | advisory panel: axiom strip + tax-stub badge |
| `tests/test_frozen.py` | `AdviceBundle`, `PmNarrative` immutable |

**CI gate:** PM purity (existing) + HNW advisory smoke + tax-stub-zero + axiom-5-`not_computed`.

---

## 8. Dependencies & build order

```text
messaging m1 (pm.advise shipped)              [shipped]
  └─ pm0 (narrative + axiom checklist)        [shipped]
       └─ pm1 (working set + rebalance_advisory) [shipped]
            └─ pm2 (dashboard + registry)      [shipped]
                 └─ portfolio_analyst pa0–pa2  [shipped — 5th leg; axiom enrichment pending]
                      └─ portfolio_optimization po0+ [planned — Addendum C]

Parallel (not blocking PM):
  tax estimate engine (TODO.md)  →  flips tax leg stub → live (no PM op/shape change)
  pm axiom enrichment (Addendum C) → score_pm_axioms consumes analyst + po0 fields
```

Full refreshed tree: **Addendum B**.

**Depends on:** messaging m0a–m1, synthetic IPS si2+ (paired fixture + `lot_positions_from_fixture`),
reconcile `as_of_date` gate (shipped). **Does not depend on:** tax estimate, QP optimizer, Phase 5.

---

## 9. HNW fixture matrix (acceptance households)

| Fixture | Source | Exercises |
| --- | --- | --- |
| Demo seed | `DEMO_HOUSEHOLD_ID` | End-to-end dashboard, rebalance loop |
| `general_hnw` rung 3 | `emit_synthetic_household` → `lot_positions_from_fixture` | 5-sleeve, liquidity tiers, IPS bands |
| `founder_executive` rung 4 | same | Concentration binds analyst + optimizer |
| `concentrated_stress` | SDG2 negation | Drift alerts; PM axiom 3 `warn`/`breach` |

PM smoke uses **in-process** fixtures for HNW (no DB) — the non-risk legs get lot-level
`LotPositionView`s via `lot_positions_from_fixture` (`synthetic/fixture_views.py`, already shipped).
Demo household uses DB bootstrap.

---

## 10. Doc updates on ship

| Doc | Update |
| --- | --- |
| [`messaging_protocol.md`](messaging_protocol.md) | §5 note: `pm.advise` scores `PmNarrative` via `decision.pm` |
| [`dev_contract_registry.md`](dev_contract_registry.md) | `portfolio_manager` track + `warehouse.decision.pm` boundary |
| [`TODO.md`](../TODO.md) | PM slices; tax-stub → live upgrade flips the leg, not the contract |

---

## 11. Self-review

### Strengths

- **No second abstraction** — specialists reached via the shipped registry; PM adds only
  working-set assembly + the axiom narrative. (Ports cut after review — they duplicated dispatch.)
- **Honest liveness** — only tax is a stub; risk/analyst/optimizer are live and labelled so.
- **Goodhart-safe diagnostic** — axiom 5 is `not_computed`, never a fabricated `pass`.
- **HNW-aligned** — whole-book working set reuses `lot_positions_from_fixture`; cohort/graph axiom
  in the acceptance matrix.
- **Advisory/acting split preserved** — PM never fuses persist or approval.

### Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| `AdviceBundle` shape churn | Additive `narrative` field; freeze locks the rest |
| Stub tax misread as real | `specialist_status.tax = stub` + dashboard badge + zero assertion |
| Axiom checklist becomes theater | `not_computed` is first-class; only measured axioms score `pass`/`warn`/`breach` |
| `decision.pm` imports risk internals | Reaches specialists via `dispatch_message` only; never imports plane cores |
| Handlers ↔ pm circular import | One-way: `handlers` → `decision.pm` → `messaging.core`/`payloads`; pm never imports handlers |

### Verdict

**pm0–pm2 shipped.** Next work: **axiom enrichment** (Addendum C) as analyst + po0 outputs land;
the `pm.advise` op and `AdviceBundle` shape stay stable — only `score_pm_axioms` and dashboard
rendering deepen.

---

## 12. Next milestone — Portfolio Optimization (§next)

PM v0 and the Portfolio Analyst slice (pa0–pa2) are shipped. The next milestone is
**portfolio optimization v1** (`portfolio_optimization_implementation.md`). Rationale:

- **Keep tax at `$0` deliberately.** `evaluate_tax_scenario → 0` is a *feature* for now, not a
  gap: a deterministic, side-effect-free tax leg lets us generate synthetic portfolios + IPS
  (`emit_synthetic_household`, cohort/rung matrix §9) and stress-test the **entire** advisory
  flow — working set → 5 legs → 7-axiom narrative → dashboard — without coupling to unfinished
  tax math. The `specialist_status.tax = stub` badge and `test_tax_scenario_stub_zero` keep this
  honest. Tax engine remains a parallel, non-blocking track (§8).
- **Analyst depth unlocks optimization.** pa0–pa2 shipped attribution, kill criteria, and NPA
  flags (`attribution.evaluate`, `policy.check`). That signal is what gives portfolio optimization
  — the genuinely **hard problem** (multi-period, tax-aware, lot-discrete, IPS-constrained) — a
  defensible objective and constraint set. Wire axiom enrichment (Addendum C) in the same window
  as po0 so the PM narrative reflects the new legs.

**Build order for the milestone:**

```text
PM v0 + analyst pa0–pa2 (shipped)  ──►  Portfolio Optimization po0+
  (tax leg held at $0 — flow-test enabler)   (constrained MV QP + Δw + RC)
        │                                         └─► pm axiom enrichment (Addendum C)
        └── tax estimate engine (parallel, non-blocking)
```

The PM contract (`pm.advise`, `AdviceBundle` shape) does **not** change — specialists enrich
the function behind their `op`, same as §3. Analyst plan:
[`portfolio_analyst_implementation.md`](portfolio_analyst_implementation.md).

---

## 13. Addendum A — Contract patch (post-ship review)

Doc corrections folded from external review (2026-06-28). Body sections above are updated;
this addendum is the audit trail.

### A.1 Tax leg does not feed PM axiom 5

**Was wrong:** §3 mapped `tax.scenario` → axiom 5 (after-tax).

**Correct:** ℍ_Allocation axiom 5 is **margin of safety at the component** (valuation buffer) —
`not_computed` until a valuation engine exists (§4). After-tax utility is first in the
[`research/portfolio_optimization.md`](research/portfolio_optimization.md) objective hierarchy,
but it is an **optimization/tax-plane concern**, not a PM axiom. When the tax estimate ships,
`tax.scenario` flips `specialist_status.tax` to `live` and feeds `optimizer.propose` / po1
after-tax μ — **no new PM axiom score**.

### A.2 Axiom 4 is "partial" — say why

Level-4 stress **does run** on the default advisory path (`evaluate_stress` replays the pinned
2008/2020/2022 sleeve-shock pack). `ScenarioSet.NONE` on `RiskRequest` controls regime overlays
for covariance priors, not whether Level-4 scenarios populate.

"Partial" means the engine uses **linear sleeve shocks with no correlation-regime spike** (PO7;
research §Multi-Asset Specifics #1). The aggregation note on `PortfolioRiskReport` states this
explicitly. Crisis-correlation enrichment is deferred to po2 (Addendum C).

### A.3 Five specialist legs (pa0 additive)

`pm.advise` nest-dispatches **five** EVALUATE ops after pa0: `risk.evaluate`, `policy.check`,
`attribution.evaluate`, `optimizer.propose`, `tax.scenario`. `AdviceBundle.attribution` is
additive (`| None` default). `score_pm_axioms` v0 does not yet consume attribution — enrichment
is Addendum C, not a contract change.

### A.4 Code hygiene

`score_pm_axioms` should stop `del payload` once enrichment reads `cohort_id` / `as_of_date`
for provenance in the narrative or axiom thresholds.

---

## 14. Addendum B — Build-order refresh

Authoritative dependency tree as of 2026-06-28 (supersedes any stale `[planned]` tags in §8).

```text
Phase 0 platform + messaging m0a–m1                    [shipped]
  └─ synthetic IPS si2+ (fixture + lot_positions)      [shipped]
       └─ portfolio_manager pm0–pm2                    [shipped]
            ├─ pm0  narrative + 7-axiom checklist
            ├─ pm1  build_working_set + rebalance_advisory
            └─ pm2  dashboard advisory panel + registry track
                 └─ portfolio_analyst pa0–pa2          [shipped]
                      ├─ pa0  attribution.evaluate + AdviceBundle.attribution
                      ├─ pa1  thesis + kill criteria
                      └─ pa2  NPA flags
                           └─ portfolio_optimization po0+     [planned — next]
                                ├─ po0  constrained MV QP + rebalance field
                                ├─ po1  turnover ‖Δw‖₁ reporting
                                └─ po2  scenario-robust Σ overlay
                                     └─ pm axiom enrichment (Addendum C)  [planned w/ po0]

Parallel (never blocking PM contract):
  tax estimate engine  →  tax.scenario stub → live (optimizer objective, not PM axioms)
  valuation engine     →  axiom 5 margin-of-safety scoring (future pm slice)
```

**Critical path now:** po0 → Addendum C enrichment in the same PR window (or immediately after).

---

## 15. Addendum C — Downstream axiom enrichment

PM v0 scores six of seven axioms from thin v0 leg outputs. Analyst pa0–pa2 and po0+ ship
richer signals **behind existing ops**. This addendum specifies how `score_pm_axioms` deepens
**without** new atomic ops, `AdviceBundle` shape churn, or `pm.advise` handler changes.

**Rule:** enrich scoring only from fields already on `AdviceBundle`; pin new thresholds to
`Settings.pm_axiom_config_version` (same pattern as the axiom-2 effective-bets fix).

| PM axiom | v0 scorer (shipped) | Enrichment source | Milestone | PO heuristic |
| --- | --- | --- | --- | --- |
| **1** whole book | `risk.report.level_1` vol > 0 | Roll up `AttributionReport.portfolio_active_return` (MV-weighted; per-lot `active_annualized` is `None` until the window clears `min_holding_years`) alongside risk — unexplained residual as unidentified risk on the unit of account | **pm-enrich-1** (w/ po0) | PO1 |
| **2** effective bets | inverse-HHI on current-book RC shares | Also score **proposed-book** RC at `OptimizationResult.rebalance.target_weights` — surface weight ≠ risk divergence | **pm-enrich-1** (po0) | PO1, PO5 |
| **3** concentration | any `concentration_alerts` → BREACH | Distinguish IPS hard breach vs **thesis-backed** concentration (`AttributionReport` + kill-criteria watch): WARN with thesis, BREACH without | **pm-enrich-2** (pa1 live) | PO5 |
| **4** survive | worst Level-4 linear stress return | Add regime-conditional stress pack (correlation spike toward +1) when po2 ships; until then keep `partial` label | **pm-enrich-4** (po2) | PO7 |
| **5** margin of safety | `not_computed` | Unchanged until valuation engine — never map tax leg here (A.1) | valuation track | — |
| **6** control exposure | `len(binding_constraints)` warn threshold | Score **feasibility at w\***: binding IPS bounds + illiquid-sleeve advisory-only Δw flags from `OptimizationResult.rebalance` | **pm-enrich-1** (po0) | PO2, PO6 |
| **7** rebalance evidence | drift rows + alerts magnitude | Gate rebalance WARN on **turnover cost**: po1 reports `‖Δw‖₁`; axiom 7 BREACH only when drift exceeds IPS band *and* net benefit unclear (PO8) | **pm-enrich-3** (po1) | PO8 |

### Suggested PR slices

| Slice | Scope | Acceptance |
| --- | --- | --- |
| **pm-enrich-1** | Axioms 1/2/6 consume `bundle.attribution` + `bundle.proposal.rebalance` | Demo + HNW rung 3: axiom 2 reflects proposed-book RC; axiom 6 surfaces illiquid Δw flag; falsifiers in `tests/test_pm_narrative.py` |
| **pm-enrich-2** | Axiom 3 thesis-aware concentration | `founder_executive` rung 4: concentrated sleeve with live thesis → WARN not BREACH |
| **pm-enrich-3** | Axiom 7 turnover gate | Drift WARN suppressed when `‖Δw‖₁` exceeds turnover budget and tax stub holds |
| **pm-enrich-4** | Axiom 4 crisis-correlation stress | po2 scenario pack wired; axiom 4 headline drops "partial" in dashboard |

### Dashboard

Each enrichment slice upgrades `render_advisory.py` — show the new sub-check (e.g. proposed RC
vs current, turnover gate, thesis badge) without implying tax numbers are live.

### Invariants preserved

- No new `op`s (`test_pm_no_new_ops` green)
- Axiom 5 stays `not_computed` until valuation engine
- Tax leg stays `stub` badge until estimate ships
- `AdviceBundle` frozen — enrichment reads existing/additive fields only

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-06-28 | Initial plan: specialist *ports* + stub envelopes, `PortfolioWorkingSet`, 4 PRs. |
| 2026-06-28 | **Review folded (Claude).** Cut the port layer (double abstraction over the messaging registry); collapsed three stub envelopes to one honest `specialist_status` (only tax is a stub); consolidated `PortfolioWorkingSet` into the existing `PmAdvisePayload`; promoted the 7-axiom checklist to pm0 with a `not_computed` honesty rule (axiom 5 = no valuation engine — Goodhart guard); added `lot_positions_from_fixture` reuse for in-process HNW; froze `AdviceBundle`; single `decision/pm.py` not a 6-file package; **4 PRs → 3**. Grounded against shipped code (`evaluate_tax_scenario` zeros, `policy.check` concentration live, `fixture_views.py`). |
| 2026-06-28 | **pm0–pm2 shipped + code review folded (Claude).** Implemented all three slices. Review fixes: (1) axiom-2 effective-bets scale bug — `pct_variance_contribution` is a [0,1] fraction, the `/100` made the diversification axiom always PASS (the exact Goodhart trap §4 warns of); removed it, demo book now correctly scores axiom 2 `breach` (~1.3 effective bets). (2) Dashboard `load_advisory_dashboard` now reuses `build_working_set` (single assembly path, no divergent manifest). (3) Axiom thresholds pinned to `Settings.pm_axiom_config_version` (audit replay). (4) Added `test_policy_check_concentration_live` + HNW rung-3 concentration assertion (§6 invariants now covered). |
| 2026-06-28 | **Next milestone re-pointed: Portfolio Analyst (not tax engine).** Tax leg stays an intentional `$0` stub — keeping `evaluate_tax_scenario → 0` lets synthetic portfolios + IPS stress-test the *whole* PM flow without waiting on the tax estimate engine. The analyst depth (attribution, kill criteria, NPA flags) feeds the harder downstream problem: **portfolio optimization**. See §next. |
| 2026-06-28 | **Addendum A/B/C (external review folded).** A.1: tax leg → no PM axiom (axiom 5 = valuation, not after-tax). A.2: axiom 4 partial = linear stress, no crisis-ρ spike. A.3: five legs after pa0. B: §8 build-order refresh — pm0–pm2 + pa0–pa2 shipped, po0+ next. C: pm-enrich-1..4 axiom scoring consumes analyst + po0 fields without op/shape churn. §12 re-pointed to portfolio optimization. |
