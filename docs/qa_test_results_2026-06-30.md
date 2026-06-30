# QA test results — qa1 through qa8

**Date:** 2026-06-30  
**Scope:** Gap backlog slices qa1–qa8 (`docs/qa_plan_implementation.md` §7)  
**Lens:** [Persona of The Software Tester](heuristics/Persona%20of%20The%20Software%20Tester.md) — weak-point hunting, independent oracles (ST2), boundary concentration (ST6), distrust of coverage-as-quality (¬QA6)

**Suite at close:** 727 tests passing (mypy clean, ruff clean)

---

## Cross-cutting pattern

Every slice found the same failure mode: **code that looked “done” but wasn’t *checked*** — untyped breaks, unguarded state jumps, model types never seeded, metrics computed but not shown, walk-forward in name only. The qa work didn’t mainly add features; it **converted implicit assumptions into loud, replayable falsifiers**.

---

## By slice

### qa1 — Execution / recon break taxonomy (P1)

**Revealed:** Multi-custodian reconciliation could open breaks as **untyped prose**. Same ISIN mapped to different tickers across custodians had no first-class break — the H5 hunt case (“break typed, not merged away”).

**What changed:** `ReconBreakType` (`stale_as_of`, `mixed_as_of`, `quantity_mismatch`, `ledger_only`, `symbology_mismatch`) + dashboard Type column. Breaks are now **classifiable and visible**, not buried in description strings.

**Falsifier:** `tests/test_phase4.py` — `test_symbology_conflict_typed_break`

**Tester read:** Tail-risk path (wrong symbology poisons the whole book) was under-tested relative to happy-path qty reconcile.

---

### qa2 — Execution / OMS cancel·replace (P2)

**Revealed:** The order state machine had **no explicit allowed-edge guard**. Hostile jumps (e.g. `filled → staged`) were possible without context-rich errors.

**What changed:** Allowed transitions are asserted; illegal edges raise with `order_id` + from/to; replace on terminal orders is blocked; cancel-after-fill is blocked.

**Falsifier:** `tests/test_phase4.py` — transition oracle + parametrized illegal edges

**What qa2 explicitly did *not* close:** **Partial fill (H4)** — still deferred in `TODO.md`. qa2 drew the boundary: all-or-nothing fills only; `test_order_partial_fill_cancel_deferred_h4` documents the open gap rather than faking coverage.

**Tester read:** ST6 at state-machine seams — the dangerous cases are illegal transitions, not the happy path.

---

### qa3 — Data / wash-sale chains (P1)

**Revealed:** Wash-sale logic passed hand-picked cases but **failed under random lot streams** — chain merge and substitute-group windows weren’t invariant-checked.

**What changed:** Property tests with an **independent chain oracle** on random streams; transitive A→B→C chains; gain harvest must not open a chain; partial-qty / window boundaries (H2 extension).

**Falsifier:** `tests/test_lot_properties.py`

**Tester read:** Interior cases were green; **edges and compositions** were where defects cluster (ST6 ⊕ RM5 tail on tax lots).

---

### qa4 — Data / corporate actions (P2)

**Revealed:** Stock splits had **no basis oracle** — qty and per-share basis could drift while total economic basis should be conserved.

**What changed:** `apply_stock_split` + hand-math and **hypothesis** falsifiers (2:1, reverse, chained splits, wrong-security isolation, metadata survival).

**Falsifier:** `tests/test_corporate_actions.py`

**Tester read:** Classic ST2 — total basis is cheap to compute independently; without it, “split applied” is observation, not verification.

---

### qa5 — Decision / optimizer QP edges (P1)

**Revealed:** The optimizer’s happy path hid **numerical and constraint tails**: near-singular Σ, all sleeves pinned min=max, zero NAV, zero turnover, single-asset book.

**What changed:** Explicit raises or pinned oracles at each edge; property hunt on singular Σ; H6/H7/E3 hunts closed.

**Falsifier:** `tests/test_optimizer_properties.py`, `tests/test_optimizer_qp.py`

**Tester read:** ¬RM4 — average-case MV rebalance was tested; **catastrophic-input** paths (infeasible, singular, zero book) were the real blast-radius gaps.

---

### qa6 — Research / walk-forward guard (P2)

**Revealed:** `WalkForwardError` only enforced **minimum window length** — not **future-data peek**. Lots acquired after `end_date` or marks dated after evaluation would still run through the backtest harness.

**What changed:** Centralized guards on lots, marks, scenario observation dates, and path index cutoffs; wired into backtest + E2E smoke first leg.

**Falsifier:** `tests/test_walk_forward_guard.py`

**Tester read:** Naming something “walk-forward safe” without date guards is **coverage theater** (¬QA6) — execution without checking.

---

### qa7 — Reporting / after-tax return YTD (P1)

**Revealed:** The client-facing metric was **computed in the backend but invisible on `/reporting`** — dashboard-first violation. Boundary cases: realized **losses** must not add tax drag; zero realized → after-tax = gross; zero cost must **not** default to a number.

**What changed:** Hand-math oracle vs events table; dashboard **After-tax YTD** column; ST6 falsifiers on loss / zero-realized / zero-NAV.

**Falsifier:** `tests/test_reporting_performance.py`

**Tester read:** qa7 was escalated to P1 because **wrong after-tax YTD reaches the client** — blast radius trumped “Reporting = medium plane.”

---

### qa8 — Data / beneficiary graph edges (P2)

**Revealed:** The domain model had `BENEFICIARY` and `beneficiary_of` **in the type system but not in the live demo graph** — cartography without terrain (model ≠ runtime).

**What changed:** Seeded IRA + trust designations; graph oracle in `test_phase1.py`; `assert_beneficiary_edges_resolve` rejects malformed edges.

**Falsifier:** `tests/test_phase1.py`

**Demo topology (independent oracle):**

```text
beneficiary_alex_smith   ──beneficiary_of──>  acct_ira
beneficiary_morgan_smith ──beneficiary_of──>  trust_smith_rev
hh_smith ──aggregates──> both beneficiaries
```

**Tester read:** Enum completeness ≠ graph correctness; **topology must be falsified** against an independent designation map.

---

## What the full qa1–qa8 arc says

| Theme | Evidence |
| --- | --- |
| **Silent success was the enemy** | Untyped breaks, unguarded OMS jumps, future marks in backtests, metrics off-dashboard |
| **Model ⊄ reality** | Beneficiary types existed; edges didn’t. Walk-forward existed; date guards didn’t. |
| **Boundaries >> interiors** | qa3 random streams, qa5 singular Σ, qa6 future injection, qa7 loss YTD |
| **Coverage % would have lied** | Green pytest + line % wouldn’t catch assertion-free or unenforced semantics (¬QA6); mutation/property/oracle work is the strong arm |
| **Explicit deferrals are findings too** | qa2 H4 partial fill, Reporting po1-tax seam — hunts filed, not silently “covered” |

---

## Registry status

All eight slices registered as **shipped** in `src/warehouse/dashboard/risk_build_registry.py` (`QA_PLAN_DELIVERABLES`). The numbered qa backlog in `docs/qa_plan_implementation.md` §7 is **complete**.

| Slice | Plane | Falsifier module |
| --- | --- | --- |
| qa1 | Execution | `tests/test_phase4.py` |
| qa2 | Execution | `tests/test_phase4.py` |
| qa3 | Data | `tests/test_lot_properties.py` |
| qa4 | Data | `tests/test_corporate_actions.py` |
| qa5 | Decision | `tests/test_optimizer_properties.py` |
| qa6 | Research | `tests/test_walk_forward_guard.py` |
| qa7 | Reporting | `tests/test_reporting_performance.py` |
| qa8 | Data | `tests/test_phase1.py` |

---

## Still open after qa8

Remaining gaps from `docs/software_testing_implementation.md` §4 — deeper work, not new qa slices:

| Plane | Gap | Notes |
| --- | --- | --- |
| **Execution** | OMS partial fill | qa2 H4 deferred (`TODO.md`) |
| **Data** | Deeper wash-chain / corporate-action edges | Beyond qa3/qa4 property coverage |
| **Research** | Full purged walk-forward loop | qa6 guards shipped; not full CV harness |
| **Reporting** | Decision tax estimator seam | po1-tax; after-tax YTD client metric is live |
| **Infra** | Postgres/Redis, migration rollback | Phase 5 |

---

## Verdict (Tester persona)

**qa1–qa8 did not prove the system is correct** — they proved where it **wasn’t yet refutable**, and closed those gaps with independent oracles so the suite **ratchets stricter** (ST8) instead of inflating a coverage number (¬QA6).
