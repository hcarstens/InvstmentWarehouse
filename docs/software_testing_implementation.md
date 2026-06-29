# Software testing — Implementation Plan

**Status:** st0 shipped (stub panel) · st1–st5 planned
**Date:** 2026-06-29
**Owner:** cross-cutting (infra + dashboard)
**Inputs:** [`heuristics/Software QA.md`](heuristics/Software%20QA.md) (QA1–QA8),
[`heuristics/Software Testing.md`](heuristics/Software%20Testing.md) (ST1–ST8),
[`research/software_testing.md`](research/software_testing.md) (framework + metrics synthesis),
[`CI.md`](../CI.md) (canonical gate)

**Baseline (2026-06-29):** 399 tests passing · 89.2% line coverage on `warehouse`
(`pytest --cov=warehouse`).

## Implementation status (current phase visibility)

All slices **not done** — none started. Build order (dashboard first for visibility):

| Slice | Item | Status |
| --- | --- | --- |
| **st0** | Dashboard panel + API + per-plane QA footnote (**top — visibility**) | ☑ done |
| **st1** | Registry + artifact schema | ☐ not done |
| **st2** | `warehouse test report` CLI (flips panel `stub`→`live`) | ☐ not done |
| **st3** | CI coverage artifact + badges + QA7 security gate | ☐ not done |
| **st4** | E2E testing — up, running, completed (priority) | ☐ not done |
| **st5** | Hard QA — optimizer / analyst / risk property + mutation (END) | ☐ not done |

Mark a slice `☑ done` here and in its §5 header when its falsifier is green on `main`.

---

## 1. Principle — evidence on the dashboard

Testing status is **living system state**, not a separate spreadsheet. Every operational plane
gets a visible pass/fail row and a coverage % that **includes unit tests** in the denominator.
Evidence shows up in **two places**: the consolidated `/testing` matrix, *and* a **QA footnote
on each plane's own dashboard page** (`/data`, `/research`, `/decision`, `/execution`,
`/reporting`, `/infra`) so a reader on a plane page sees that plane's test pass/fail and
coverage % without leaving it.

| Axiom | Application |
| --- | --- |
| QA1 Shift-left | Plane test paths registered before features ship; falsifier required per deliverable |
| QA2 Automation primacy | `pytest` on every PR; dashboard reads last CI/local report artifact |
| QA3 Risk-based | Floors weighted by blast radius — Data + Decision highest |
| QA4 CI integration | Coverage JSON artifact uploaded alongside green `pytest` |
| QA6 Metrics-driven | Per-plane coverage + pass rate on `/testing`; no org-wide coverage gaming |
| QA7 Security as quality | Secret scan + dependency audit (`pip-audit`) in CI; security is a test gate, not an afterthought |
| ST2 Oracle | Falsifier tests use independent expected values, not copied optimizer output |
| ST3 Coverage insufficiency | Coverage % is a **gap-finder badge**, never gates `ok`; mutation kill % measures real discriminating power on critical planes |
| ST4 Pyramid | ~70% unit · ~25% integration/workflow · ~5% E2E smoke + HTTP (measured, not assumed) |
| ST5 Determinism | Seeded synthetic fixtures; session-scoped SQLite in `conftest.py` |
| ST6 Boundary + property | Property-based (`hypothesis`) invariants on optimizer, lot, and risk math; generators hunt boundaries |
| ST8 Regression | Every escaped defect → failing test first; register in testing registry |

**Precedent panels:** Risk build tracker (`risk_build_registry.py` → `/risk`) and E2E smoke
matrix (`e2e_data.py` → Research plane). The testing dashboard follows the same
**registry → data loader → renderer → API → page** pattern.

```text
testing_registry.py          # plane → pytest paths → coverage glob → floor
  → testing_data.py          # load artifact OR warehouse test report
  → render_testing.py        # HTML table  (consolidated /testing matrix)
  →   render_qa_footnote()   # one-line per-plane badge, reused by every pages/*.py
  → GET /api/testing         # JSON for automation
  → /testing                 # dashboard page (Infra nav or dedicated route)
  → /data /research /decision /execution /reporting /infra   # each shows its QA footnote
```

---

## 2. Scope — what ships vs deferred

### In scope (v1 testing dashboard)

| Item | Rationale |
| --- | --- |
| `testing_registry.py` — one row per operational plane + infra + cross-cutting | Single source of truth for plane → test mapping |
| `load_testing_report()` — pass/fail + coverage % + coverage badge per plane | Dashboard-first; includes unit tests in coverage; coverage is a badge, not a gate (ST3) |
| `warehouse test report` CLI | Writes `runs/testing/last_report.json` (gitignored) |
| `/testing` page + `GET /api/testing` | Living status report |
| `render_qa_footnote(plane_id)` on every plane page (`pages/*.py`) | QA test pass/fail + coverage % footnote per plane; reads same artifact, no re-run |
| CI: `pytest --cov=warehouse --cov-report=json` artifact | Refresh dashboard without re-running full suite on every page view |
| CI security gate: `pip-audit` + secret scan (`detect-secrets`) | QA7 — public repo + tax/client data; vuln/credential leak fails the `test` job |
| Add `hypothesis` to `[dev]` deps; property-based invariants on optimizer/lot/risk | ST6 — generators hunt boundaries no hand-written case enumerates |
| Mutation kill % column for critical planes (Data, Decision) — **report, don't gate** | ST3 — proves coverage means checked behavior, not just executed |
| Extend `CI.md` + `scripts/ci.sh test` | Local/Actions parity |
| Register panel in `phases.py`, `navigation.py` | Dashboard-first rule |

### Deferred

| Item | Why |
| --- | --- |
| Hard CI gate on per-plane coverage floors | Coverage **never** gates `ok` (ST3); floors are amber badges only. A future gate, if any, is on mutation kill %, not line % |
| Mutation testing **gate** (`mutmut`) | Kill % is reported on Data + Decision in st5 (final slice); *gating* on it is deferred until baselines stabilize |
| Full-repo mutation + SAST (`bandit`/`semgrep`) | Critical-plane mutation + `pip-audit`/secret scan ship first; deep SAST is Phase 5 |
| Playwright / browser E2E | HTTP tests in `test_dashboard.py` sufficient for Phases 0–4 |
| Per-PR dashboard refresh on every `warehouse serve` | Too slow; artifact + stale badge instead |
| Branch coverage floors | Line coverage first; branch targets after reporting plane ships |
| Defect escape rate automation | Manual JOURNAL entry until incident tooling exists |

---

## 3. Test pyramid

```text
                    ┌─ E2E smoke matrix (4 cohorts × N legs)     ─┐  thin
                    ├─ Integration: synthetic → pm.advise          ─┤
                    └─ Dashboard HTTP (plane pages 200 + JSON)     ─┘
              ┌─ Workflow: phase1–4, daily_refresh, messaging       ─┐  medium
              └─ Risk falsifiers: v0a–v1.2, si0–si4                  ─┘
    ┌─ Unit + property-based: optimizer, IPS, risk API, models, lot ledger ─┐  base
    └─ Architecture guards: plane boundaries, workflow catalog             ─┘
```

| Layer | Share of suite | Gate |
| --- | --- | --- |
| Unit + property-based (`hypothesis`) | ~70% | Every PR (`pytest`) |
| Integration / workflow | ~25% | Every PR |
| E2E smoke + HTTP | ~5% | PR + live Research panel |

Shares are **targets**; st1 measures the actual mix (count by directory/marker) and the
`/testing` panel shows actual vs target so ST4 stays falsifiable, not assumed.

---

## 4. Per-plane testing pass

Coverage figures are **line %** from `pytest --cov=<package>` including all unit tests that
execute code in that package. Floors are gap-finder **badges** (ST3) — they color the panel
amber but never set `ok=false`. On the two critical planes (Data, Decision) a **mutation
kill %** (`mutmut`) is reported alongside coverage so the panel shows whether covered lines
are actually *checked*, not merely executed. Math-heavy seams carry **property-based
invariants** (`hypothesis`, ST6) — see the Property column.

### 4.1 Data (`warehouse.data`) — baseline 85.7% · floor 90% (badge) · mutation **reported** · readiness `live`

**Blast radius:** Wrong lots or symbology poison every downstream plane. Critical plane —
mutation kill % reported on `lot_ledger` math.

| Area | Oracle | Primary tests | Gaps |
| --- | --- | --- | --- |
| Entity graph | Known topology | `test_phase1.py`, `test_architecture.py` | Beneficiary edges |
| Security master | Tax character, wash groups | `test_architecture.py` | Corporate actions |
| Lot ledger | qty × basis, holding period | `test_phase2.py` | Wash-sale chain boundaries |
| **Lot ledger (property)** | **Invariants: basis ≥ 0, Σ lot qty = position qty, holding-period monotonic in date** | **`test_lot_properties.py` (hypothesis, ST6)** | **Wash-chain merge under random lot streams** |
| Custodian ingest | Parsed rows → positions | `test_phase2.py` | Malformed file → surfaced error |
| Schema / views | Migration version | `test_phase1.py` | — |

```bash
pytest tests/test_phase1.py tests/test_phase2.py tests/test_architecture.py -q
```

### 4.2 Research (`warehouse.research`) — baseline 95.4% · floor 93% · readiness `live`

**Blast radius:** Lookahead in backtests, wrong risk numbers, synthetic fixtures that don't
stress bindings.

| Area | Oracle | Primary tests | Gaps |
| --- | --- | --- | --- |
| Risk API v0/v1 | Contract envelopes | `test_risk_*.py` (12 files) | Overlay edge cases |
| **Risk math (property)** | **Invariants: vol ≥ 0, corr ∈ [−1, 1], VaR ≤ CVaR, sub-additivity of diversified risk** | **`test_risk_properties.py` (hypothesis, ST6)** | **Degenerate covariance, single-asset book** |
| HNW synthetic | SDG axioms, cohort matrix | `test_hnw_synthetic.py`, asset suite | New asset types |
| Synthetic IPS | `validate_ips`, binding matrix | `test_synthetic_ips*.py`, IPS tests | si5+ as shipped |
| Walk-forward | Purge days, no future data | Config + partial tests | Explicit `WalkForwardError` |
| E2E smoke legs | Independent drift/optimizer/PM | `workflow_smoke.py`, integration | Dashboard mirrors pytest |

```bash
pytest tests/test_risk_*.py tests/test_hnw_synthetic.py tests/test_synthetic_ips*.py \
  tests/test_ips_*.py tests/integration/test_end_to_end_synthetic.py -q
```

#### 4.2.1 Synthetic portfolio + IPS builders — acceptance items

The builders (`research/synthetic/{ips_emit,ips_cohort,ips_validate}.py`,
`research/risk/synthetic.py`, `infra/db/synthetic_seed.py`) are **generators** — their oracle is
acceptance axioms, not a copied expected value (ST2). Tests split by cost and by what they gate:

**Structural — prerequisite for trustworthy E2E (lands in/with st4).** The smoke matrix consumes
generated households + IPS, so these must be green first (S5 universality, S7 immediate error):

| Item | Oracle / invariant | Test |
| --- | --- | --- |
| Per-SDG-axiom acceptance | One isolated assertion **per SDG axiom** (S2/S3 — not one blob) | `test_hnw_synthetic.py` (one test per axiom) |
| Emit → validate round-trip | `validate_ips(ips_emit(cohort))` passes clean for every cohort (S4 transparency) | `test_synthetic_ips.py` |
| Cohort coverage | Each cohort row yields a structurally valid IPS; binding matrix has no empty cell | `test_synthetic_ips_integration.py` |
| Determinism | Same seed → byte-identical portfolio + IPS; reorder-independent (ST5) | `test_hnw_synthetic.py` |
| Boundary / error surfacing | Zero sleeves, max concentration, conflicting constraints → **raises**, never silently clips (ST6, S7) | `test_synthetic_ips_workflow.py`, `test_ips_sleeves.py` |

**Statistical — deep validation of synthetic paths (lands in st5, hard QA).** Expensive, high-rigor:

| Item | Oracle / invariant | Test |
| --- | --- | --- |
| Distributional validity | Synthetic daily paths match target **vol clustering, kurtosis, autocorrelation** within tolerance | `test_synth_distribution.py` (new) |
| Null baselines | Generator output **beats** shuffle + bootstrap nulls — fixtures actually stress bindings | `test_synth_null_baseline.py` (new) |
| SDG3 retire falsifier | Axioms-**disabled** generator must **underperform** full generator on downstream pass rate (else axioms add no value) | `test_synth_sdg_ablation.py` (new) |
| Cross-regime | Synthetic-tuned rule must clear the **2022–2025 bear** cross-regime check before ship (no synthetic-only approval) | `test_synth_cross_regime.py` (new) |

```bash
# structural (st4 prerequisite)
pytest tests/test_hnw_synthetic.py tests/test_synthetic_ips*.py tests/test_ips_*.py -q
# statistical (st5 hard QA)
pytest tests/test_synth_distribution.py tests/test_synth_null_baseline.py \
  tests/test_synth_sdg_ablation.py tests/test_synth_cross_regime.py -q
```

### 4.3 Decision (`warehouse.decision`) — baseline 94.7% · floor 93% (badge) · mutation **reported** · readiness `live`

**Blast radius:** Wrong weights, silent constraint violations, tax seams, gates bypassed.
Critical plane — mutation kill % reported on `optimizer/qp.py`.

| Area | Oracle | Primary tests | Gaps |
| --- | --- | --- | --- |
| IPS monitor | Drift vs IPS | `test_phase3.py`, synthetic workflow | Liquidity sleeve transitions |
| Optimizer v1 (po0–po2) | QP KKT, turnover, robust stress | `test_optimizer_*.py` | MIP when shipped |
| **Optimizer (property)** | **Invariants: Σ weights = 1, long-only ⇒ wᵢ ≥ 0, turnover ≤ bound, feasible ⇒ no constraint violated, more risk-aversion ⇒ lower variance** | **`test_optimizer_properties.py` (hypothesis, ST6)** | **Near-singular Σ, all-constraints-binding** |
| Tax overlay | Tax delta vs baseline | `test_optimizer_tax_seam.py` | STCG/LTCG date boundaries |
| PM / analyst | Narrative, NPA, attribution | `test_pm_*.py`, `test_analyst_*.py` | Kill-criteria edges |
| Orchestrator | Office Manager gate | `test_orchestrator.py` | — |

```bash
pytest tests/test_phase3.py tests/test_optimizer_*.py tests/test_pm_*.py \
  tests/test_analyst_*.py tests/test_orchestrator.py -q
```

### 4.4 Execution (`warehouse.execution`) — baseline 88.5% · floor 90% · readiness `live`

**Blast radius:** Staged orders without recon truth; post-trade breaks invisible.

| Area | Oracle | Primary tests | Gaps |
| --- | --- | --- | --- |
| Reconciliation | Break count, lot alignment | `test_phase2.py`, `test_phase4.py` | Multi-custodian taxonomy |
| OMS staging | Order state machine | `test_phase4.py` | Cancel/replace boundaries |
| Daily refresh | Timeline steps | `test_phase2.py` | Failed step in panel |

```bash
pytest tests/test_phase2.py tests/test_phase4.py -q
```

### 4.5 Reporting (`warehouse.reporting`) — baseline 0% · floor 80% · readiness `partial`

**Blast radius:** Tax and performance reports wrong with no tests — **highest priority gap**.

| Area | Oracle | Primary tests | Gaps |
| --- | --- | --- | --- |
| Performance | Known return series | **None** | Module stub only |
| Tax scenarios | Scenario → liability | Interim via `test_phase4.py` (decision tax) | Reporting-plane ownership |

**Interim pass** (tax logic in decision until reporting ships):

```bash
pytest tests/test_phase4.py -k tax -q
```

**Rule:** Do not mark Reporting plane `live` in `status.py` until dedicated
`tests/test_reporting_*.py` exists and floor ≥ 80%.

### 4.6 Infrastructure (`warehouse.infra`) — baseline 86.6% · floor 85% · readiness `live`

| Area | Oracle | Primary tests | Gaps |
| --- | --- | --- | --- |
| Health checks | Each check pass/fail | `test_infra_health.py` | Postgres/Redis (Phase 5) |
| DB bootstrap / seed | Idempotent demo household | `conftest.py` session fixture | Migration rollback |
| Config | Frozen settings | `test_config.py`, `test_frozen.py` | — |

```bash
pytest tests/test_infra_health.py tests/test_config.py tests/test_frozen.py -q
```

### 4.7 Cross-cutting — baseline 83.7% · floor 80%

Packages: `workflows`, `messaging`, `orchestrator`, `models`, `dashboard`, `config`, `integrity`.

| Seam | Guard | Tests |
| --- | --- | --- |
| Messaging core | Plane-free imports | `test_messaging_*.py`, `test_architecture.py` |
| Workflows | Six core workflows | `test_architecture.py` |
| Dashboard | Plane routes 200 | `test_dashboard.py` |
| Integration | Generated household → stack | `test_end_to_end_synthetic.py` |

```bash
pytest tests/test_messaging_*.py tests/test_dashboard.py \
  tests/integration/test_end_to_end_synthetic.py -q
```

### 4.8 Per-plane QA footnote (on each plane page)

Each plane's dashboard page ends with a one-line QA footnote, rendered by a single shared
helper `render_qa_footnote(plane_id)` and fed by the same `load_testing_report()` artifact
(no test run on page view). One footnote per page — no copy-paste logic.

| Field | Source | Display |
| --- | --- | --- |
| Pass/fail | `plane.passed` / `plane.tests` | ✓ green `23/23 passing` · ✗ red `21/23 — 2 failing` |
| Coverage % | `plane.coverage_pct` vs `coverage_floor_pct` | `85.7%` (amber ⚠ if `< floor`, with `floor 90%`) |
| Mutation kill % | `plane.mutation_kill_pct` (critical planes only) | `kill 78%` (omitted when `None`) |
| Stale / link | report `stale`; deep-link to `/testing` | `stale — run warehouse test report` · "full matrix →" |

Rendered example (Data page footer):

```text
QA · ✓ 23/23 passing · coverage 85.7% ⚠ (floor 90%) · mutation kill 78% · full matrix →
```

| Page | Footnote `plane_id` |
| --- | --- |
| `pages/data.py` (`/data`) | `data` |
| `pages/research.py` (`/research`) | `research` |
| `pages/decision.py` (`/decision`) | `decision` |
| `pages/execution.py` (`/execution`) | `execution` |
| `pages/reporting.py` (`/reporting`) | `reporting` |
| `pages/infra.py` (`/infra`) | `infra` |

**Rule:** the footnote reflects the **same** `ok` semantics as §8 — coverage below floor shows
an amber badge but does **not** render the footnote red; only test failures do (ST3).

---

## 5. Implementation slices

### st0 — dashboard panel + API  ☑ **done**  *(~1 PR — TOP, for phase visibility)*

**Goal:** a **visible testing panel at `warehouse serve` first** (dashboard-first, CLAUDE.md) so
current project phase is on screen from day one. Ships with the panel **wired but reading
sample/empty-state data** until st1/st2 feed the real report; panel status starts `stub`,
flips to `live` once st2 writes a report.

| Task | Acceptance |
| --- | --- |
| `load_testing_report()` reads artifact if present, else empty-state | No artifact → "no report yet — run `warehouse test report`"; never crashes |
| `render_testing.py` | Table: Plane · Tests · Pass · Fail · Coverage % (amber if < floor) · Mutation kill % (critical planes) · Status. Headline: pass rate + `planes_below_floor` + actual-vs-target pyramid |
| `render_qa_footnote(plane_id)` in `render_testing.py` | One-line badge per §4.8; added to every `pages/*.py` footer |
| `GET /api/testing` | JSON matches §8 schema (empty-state shape valid too) |
| `/testing` route (or Infra sub-panel) | Linked from catalog nav |
| Register in `phases.py`, `navigation.py` | Panel `Testing matrix` status `stub` → `live` after st2 |
| `tests/test_dashboard.py` | `/testing` returns 200; API JSON valid (incl. empty state); **each plane page renders its QA footnote** |

**Falsifier:** `pytest tests/test_dashboard.py -k "testing or qa_footnote"` — panel + every plane
footnote render with and without a report present

### st1 — registry + artifact schema  ☐ **not done**  *(~1 PR)*

**Goal:** single source of truth for plane → tests → coverage glob; feeds the st0 panel.

| Task | Acceptance |
| --- | --- |
| Add `src/warehouse/dashboard/testing_registry.py` | `PlaneTestSlice` rows for all 5 planes + infra + cross-cutting |
| Define `TestingReport` / `PlaneTestResult` Pydantic models in `testing_data.py` | JSON-serializable; `ok = failed == 0` (coverage never gates, ST3); `coverage_status` badge; overall `ok = all(plane.ok)` |
| Map `pytest_paths` per plane (see §4) | Matches `CI.md` § "By plane / phase" |
| Map `coverage_glob` per plane | `src/warehouse/data/**`, etc. |
| Measure actual pyramid mix (count by dir/marker) | Stored on report as `pyramid: {unit, integration, e2e}` for actual-vs-target (ST4) |
| Unit test registry completeness | `tests/test_testing_registry.py` — every `PLANES` entry has a slice |

**Falsifier:** `pytest tests/test_testing_registry.py`

### st2 — `warehouse test report` CLI  ☐ **not done**  *(~1 PR)*

**Goal:** generate `runs/testing/last_report.json` without starting the HTTP server; flips the
st0 panel from `stub` to `live`.

| Task | Acceptance |
| --- | --- |
| `warehouse test report` in `cli.py` | Runs full `pytest --cov=warehouse --cov-report=json` |
| Per-plane coverage aggregation | Line % from coverage JSON bucketed by package prefix |
| Per-plane pass/fail | Subprocess `pytest <paths> -q` per registry row (or node-id collect) |
| Write `runs/testing/last_report.json` | Includes `generated_at`, `git_sha` (if available), overall + planes |
| Write `runs/testing/coverage.json` | Full coverage artifact for drill-down |

**Falsifier:** `pytest tests/test_testing_report.py` — CLI produces valid report on fixture subset

### st3 — CI coverage artifact + soft floors  ☐ **not done**  *(~1 PR)*

**Goal:** CI uploads coverage; warn when plane below floor.

| Task | Acceptance |
| --- | --- |
| Extend `.github/workflows/ci.yml` `test` job | `pytest --cov=warehouse --cov-report=json:coverage.json` |
| Upload `coverage.json` + `runs/testing/last_report.json` as artifact | 7-day retention |
| Extend `scripts/ci.sh test` | Same flags as Actions |
| Coverage badge only — **never fail on line %** (ST3) | Plane < floor → amber `coverage_status="below_floor"`, `ok` unaffected |
| **Security gate**: add `pip-audit` + `detect-secrets` to `test` job (QA7) | High/critical vuln or detected secret **fails** the job |
| Update `CI.md` | Document coverage commands, security gate, artifact paths |

**Falsifier:** CI `test` job green; coverage artifact present on PR; seeded fake secret / known-vuln dep makes the security step **red**

### st4 — E2E testing: up, running, and completed  ☐ **not done**  *(priority — do first after dashboard)*

**Goal:** the cross-plane smoke path is fully green and mirrored on the dashboard before any
deep per-plane correctness work begins. Prove the wiring end-to-end first (ST4 — the thin top
layer must exist and pass), then deepen the base (st5).

| Task | Acceptance |
| --- | --- |
| **Synthetic/IPS structural tests first** (§4.2.1) | Per-axiom SDG, emit→validate round-trip, cohort coverage, determinism, error-surfacing all green — E2E consumes these, so they gate it |
| Complete E2E smoke matrix | All 4 cohorts × N legs run green: synthetic household → drift → optimizer → PM advise |
| Independent legs (no shared mutable state) | Each leg has its own oracle; ST5 deterministic (seeded), order-independent |
| Dashboard mirrors pytest | Research plane E2E panel (`e2e_data.py`) reflects last run; no drift between panel and `pytest` |
| Wire into CI `test` job | E2E smoke runs every PR; failure blocks merge |
| `/testing` shows `E2E smoke pass %` = 4/4 | Headline metric green |

**Falsifier:** `pytest tests/integration/test_end_to_end_synthetic.py tests/test_*smoke* -q`
green; `/testing` reports 4/4 cohorts.

### st5 — hard QA: deep correctness tests  ☐ **not done**  *(end — after E2E green)*

**Goal:** the expensive, high-rigor per-plane work — optimizer, analyst/PM, risk math, mutation.
These are **deferred to the end on purpose**: they are slow to author and run, and only worth
the investment once the suite, dashboard, and E2E wiring (st0–st4) are stable.

| Order | Plane | Target tests |
| --- | --- | --- |
| 1 | Reporting | `tests/test_reporting_performance.py` when module ships |
| 2 | Cross-cutting | `test_dashboard.py` for `/testing` + QA footnote render sections |
| 3 | Execution | Recon break taxonomy |
| 4 | Data | `tests/test_lot_properties.py` — `hypothesis` lot invariants (ST6); ingest error propagation |
| **5 (last)** | Decision — optimizer | `tests/test_optimizer_properties.py` — `hypothesis` invariants (Σw=1, long-only ≥0, turnover ≤ bound, feasibility, monotone risk-aversion) (ST6) |
| **6 (last)** | Decision — analyst/PM | Deepen `test_analyst_*.py` / `test_pm_*.py`: kill-criteria edges, NPA boundaries, attribution oracles |
| **7 (last)** | Research — risk | `tests/test_risk_properties.py` — `hypothesis` risk invariants (VaR ≤ CVaR, corr bounds, sub-additivity) (ST6) |
| **8 (last)** | Research — synthetic paths | Statistical validation (§4.2.1): distributional checks, null baselines, SDG3 ablation falsifier, 2022–2025 cross-regime |
| **9 (last)** | Data + Decision | Mutation kill % reported on `lot_ledger` + `optimizer/qp.py` (`mutmut`, report-only, ST3) |

Mark st5 sub-slices `shipped` in `testing_registry.py` when property suites green + floors met.
**Optimizer, analyst, and risk testing land last** — highest rigor, highest cost; sequence them
after E2E so the cheap wiring failures surface before the expensive deep tests are written.

---

## 6. Registry schema

```python
class PlaneTestSlice(BaseModel):
    plane_id: str           # data | research | decision | execution | reporting
    name: str               # display name
    package: str            # warehouse.data
    pytest_paths: list[str] # relative to repo root
    coverage_glob: str      # src/warehouse/data/**
    coverage_floor_pct: float   # amber-badge threshold ONLY — never gates ok (ST3)
    risk_tier: str          # critical | high | medium
    report_mutation: bool = False   # critical planes: report mutmut kill % (ST3)
    mutation_targets: list[str] = []  # e.g. ["src/warehouse/decision/optimizer/qp.py"]
    property_paths: list[str] = []    # hypothesis suites for this plane (ST6)
    note: str = ""


PLANE_TEST_SLICES: list[PlaneTestSlice] = [
    PlaneTestSlice(
        plane_id="data",
        name="Data",
        package="warehouse.data",
        pytest_paths=[
            "tests/test_phase1.py",
            "tests/test_phase2.py",
            "tests/test_architecture.py",
        ],
        coverage_glob="src/warehouse/data/**",
        coverage_floor_pct=90.0,
        risk_tier="critical",
        report_mutation=True,
        mutation_targets=["src/warehouse/data/lot_ledger.py"],
        property_paths=["tests/test_lot_properties.py"],
    ),
    # ... research, decision, execution, reporting, infra, cross_cutting
    # decision: report_mutation=True,
    #           mutation_targets=["src/warehouse/decision/optimizer/qp.py"],
    #           property_paths=["tests/test_optimizer_properties.py"]
]
```

**Link to deliverable falsifiers:** `risk_build_registry.py` `falsifier_test` fields remain
authoritative for shipped slices. Testing registry is the **plane-level** rollup; risk build
tracker is the **slice-level** drill-down.

---

## 7. Coverage aggregation

Per-plane line coverage **includes unit tests**:

1. Run `pytest --cov=warehouse --cov-report=json` (full suite or plane subset).
2. Bucket `coverage.json` files by package prefix:

   | Bucket | Prefix |
   | --- | --- |
   | Data | `src/warehouse/data/` |
   | Research | `src/warehouse/research/` |
   | Decision | `src/warehouse/decision/` |
   | Execution | `src/warehouse/execution/` |
   | Reporting | `src/warehouse/reporting/` |
   | Infra | `src/warehouse/infra/` |
   | Cross-cutting | `workflows/`, `messaging/`, `orchestrator/`, `models/`, `dashboard/`, `config`, `integrity/`, `cli` |

3. `coverage_pct = 100 × (num_statements - missing_lines) / num_statements`.

**Overall row:** full `warehouse` package — must match sum semantics of CI artifact.

**Stale detection:** compare `git_sha` in artifact to `git rev-parse HEAD`; if mismatch,
panel shows stale badge and last-known metrics (do not re-run 399 tests on page load).

---

## 8. API shape

`GET /api/testing` (and `load_testing_report()` return type):

```json
{
  "generated_at": "2026-06-29T12:00:00Z",
  "git_sha": "abc123def",
  "stale": false,
  "pyramid": { "unit_pct": 70, "integration_pct": 25, "e2e_pct": 5 },
  "overall": {
    "tests": 399,
    "passed": 399,
    "failed": 0,
    "coverage_pct": 89.2,
    "planes_below_floor": 3,
    "ok": false
  },
  "planes": [
    {
      "plane_id": "data",
      "name": "Data",
      "tests": 23,
      "passed": 23,
      "failed": 0,
      "coverage_pct": 85.7,
      "coverage_floor_pct": 90.0,
      "coverage_status": "below_floor",
      "mutation_kill_pct": 78.0,
      "risk_tier": "critical",
      "ok": true,
      "pytest_paths": ["tests/test_phase1.py", "tests/test_phase2.py", "tests/test_architecture.py"]
    }
  ]
}
```

**`ok` semantics (ST3 — coverage never gates):**

- **Per plane:** `ok = (failed == 0)`. Coverage does **not** enter `ok`. A plane with all
  tests green but coverage below floor is `ok=true` with `coverage_status="below_floor"`
  (amber badge — a gap-finder, not a failure). Above, Data passes all 23 tests → `ok=true`,
  even though 85.7% < 90% floor shows an amber coverage badge.
- **`coverage_status`:** `"ok"` if `coverage_pct >= coverage_floor_pct` else `"below_floor"`.
- **`mutation_kill_pct`:** present only on planes with `report_mutation=True` (Data, Decision);
  reported, never gates.
- **Overall:** `ok = all(plane.ok for plane in planes) and overall.failed == 0`. A red plane
  turns the top line red — no green headline sitting over failing planes. `planes_below_floor`
  surfaces coverage gaps in the headline without conflating them with test failures.

---

## 9. Metrics card

Track on dashboard and append to `runs/testing/history.jsonl` (gitignored):

| Metric | Purpose | Target |
| --- | --- | --- |
| Pass rate | Suite health (gates `ok`) | 100% on `main` |
| Line coverage % (per plane) | Gap-finder **badge** (ST3) — never gates | Plane floors (§4), amber if below |
| Mutation kill % (Data, Decision) | Real discriminating power (ST3) | Reported; rising trend, no hard gate yet |
| Pyramid mix (actual vs target) | Feedback-loop shape (ST4) | ≈70/25/5; alarm on E2E inversion |
| Flake rate | Trust (ST5) | 0 — quarantine is P1 |
| Falsifier green % | Deliverable honesty | 100% shipped slices in risk registry |
| Security: open high/critical vulns + leaked secrets | QA7 | 0 — fails CI `test` job |
| E2E smoke pass % | Cross-plane wiring | 4/4 cohorts in smoke matrix |
| CI duration | Feedback loop (ST4) | < 15 min |
| Defect escape rate | Outcome (QA6) | Manual — `JOURNAL.md` |

**Do not** set a repo-wide "90% or fail" line-coverage gate — it is the weak arm in every
`research/software_testing.md` falsifier. Discriminating power comes from **mutation kill %**
and **property-based invariants**, which is what the dashboard elevates instead.

---

## 10. Test authoring conventions

| Rule | Source |
| --- | --- |
| Oracle before assertion — independent expected value | ST2 |
| Boundary values: zero NAV, empty portfolio, max concentration, wash window | ST6 |
| Property-based (`hypothesis`) for optimizer/lot/risk math — state invariants, let generators hunt boundaries and shrink to minimal failing case; seed with `derandomize` for determinism | ST6 + ST5 |
| Never commit secrets/client data; `detect-secrets` + `pip-audit` in CI | QA7 + `CLAUDE.md` |
| Seed RNG (`seed=42`); session DB fixture; no network in unit tests | ST5 |
| Bug fix starts red → green; register falsifier | ST8 |
| New frozen types → `FROZEN_TYPES` + `test_frozen.py` | `CLAUDE.md` |
| No silent fallbacks in tests — failures must propagate | `CLAUDE.md` errors-bubble |

---

## 11. Dependencies & build order

```text
st0 (dashboard panel + API + QA footnote — stub data)   ← TOP, phase visibility
  → st1 (registry + models)
    → st2 (CLI report writer — flips panel stub→live)
      → st3 (CI artifact + badges + security gate)
        → st4 (E2E testing — up, running, completed)   ← priority
          → st5 (hard QA — optimizer / analyst / risk / mutation)   ← END
```

**Sequencing rationale:** the **dashboard panel ships first (st0)** with stub/empty-state data so
project phase is visible immediately (dashboard-first, CLAUDE.md); st1 (registry) + st2 (CLI)
then feed it real data and flip it `stub`→`live`. Among the test-deepening work, **E2E (st4)
proves cross-plane wiring cheaply before** the hard, high-cost correctness tests (st5 —
optimizer, analyst, risk, mutation), which land **last**.

**Parallel safe:** the st5 reporting/cross-cutting/execution gap tests can land earlier if they
only add pytest files. The deep optimizer/analyst/risk property + mutation work stays at the end.

**Existing gates unchanged:**

```bash
ruff check src tests && ruff format --check src tests && mypy src/warehouse && pytest
```

st3 **adds** `--cov` flags to the test step; does not remove lint/types jobs.

---

## 12. Test plan summary (this epic)

| File | Covers |
| --- | --- |
| `tests/test_testing_registry.py` | Registry complete; floors sane; paths exist; `report_mutation`/`property_paths` resolve |
| `tests/test_testing_report.py` | CLI + aggregation; JSON schema; `ok` not gated on coverage; overall = `all(plane.ok)` |
| `tests/test_dashboard.py` | `/testing` HTTP + `/api/testing` JSON; QA footnote present on every plane page (§4.8) |
| `tests/test_optimizer_properties.py` | ST6 — optimizer invariants (Σw=1, ≥0, turnover, feasibility, monotone risk-aversion) |
| `tests/test_lot_properties.py` | ST6 — lot ledger invariants |
| `tests/test_risk_properties.py` | ST6 — risk math invariants |
| `tests/test_synth_distribution.py` · `_null_baseline.py` · `_sdg_ablation.py` · `_cross_regime.py` | §4.2.1 — synthetic path statistical validation (st5) |
| Existing synthetic/IPS tests (`test_hnw_synthetic.py`, `test_synthetic_ips*.py`, `test_ips_*.py`) | §4.2.1 structural — gate E2E (st4); extend per-axiom + round-trip + determinism |
| Existing plane tests (§4) | Unchanged — become registry `pytest_paths` |

**CI gate (st3+):** full `pytest` green (includes property suites); coverage artifact
uploaded (badge only, no coverage gate); **security step fails on high/critical vuln or
leaked secret**; mutation kill % reported (not gated).

---

## 13. Doc updates on ship

| Doc | Update |
| --- | --- |
| [`CI.md`](../CI.md) | Coverage commands; artifact paths; `/api/testing` smoke |
| [`CLAUDE.md`](../CLAUDE.md) | Link testing dashboard under Commands |
| [`TODO.md`](../TODO.md) | Close testing dashboard item; per-plane gap backlog |
| [`research/software_testing.md`](research/software_testing.md) | Mark implementation plan linked |
| [`dev_contract_registry.md`](dev_contract_registry.md) | Register `testing` track if new boundary |

---

## 14. Self-review

### Strengths

- **Dashboard-first** — matches risk build tracker and E2E smoke precedent; QA evidence shows
  both in the `/testing` matrix and as a pass/fail + coverage footnote on each plane page (§4.8).
- **Unit-inclusive coverage** — per-plane % reflects real pytest execution, not a separate metric.
- **Coverage never gates `ok`** — line % is an amber gap-finder badge (ST3); discriminating
  power comes from mutation kill % + property-based invariants, the strong arm in the research
  falsifiers. No green headline over failing planes (`overall.ok = all(plane.ok)`).
- **E2E first, hard QA last** — st4 gets the cross-plane smoke path up, running, and completed
  before st5's expensive optimizer/analyst/risk property + mutation work; cheap wiring failures
  surface before deep tests are authored.
- **Property-based math tests (ST6)** — optimizer/lot/risk invariants catch boundary defects no
  hand-written case enumerates; sequenced last (st5) given authoring/run cost.
- **Security as a gate (QA7)** — `pip-audit` + secret scan fail CI; correct for a public repo
  holding tax/client data.
- **Incremental PRs** — st0–st4 shippable independently; st5 is the final deep-correctness slice.

### Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Full pytest on every page load | Artifact + stale badge; `warehouse test report` refresh |
| Per-plane pytest subprocess slow in CLI | st2 runs full suite once; plane rows derived from node collection + coverage buckets |
| Coverage bucket overlap (e.g. phase2 tests touch data + execution) | Overall suite coverage for plane %; plane `pytest_paths` for pass/fail only |
| Reporting 0% reads as green | Coverage badge shows `below_floor` amber; plane stays `partial` in `status.py` until `test_reporting_*.py` exists — but `ok` tracks test failures, so it is not falsely red either |
| Mutation/property tests slow CI | Property suites run every PR (fast, `derandomize`); `mutmut` runs nightly or on-demand, report-only — never on the PR critical path |
| Flaky tests erode trust | ST5 — zero tolerance; quarantine = P1 |

### Verdict

Plan is **ready to execute** starting with **st0 (dashboard panel — for phase visibility)**.
Estimated **3–4 PRs** for dashboard + CI artifact. Critical path: **st0 (dashboard) → st1
(registry) → st2 (CLI) → st3 (CI) → st4 (E2E)**; the hard QA work (**st5** — optimizer, analyst,
risk, mutation) is the **final** slice. Ship the visible panel first, then E2E up/running/
completed, then defer the expensive deep correctness tests to the end. **Nothing is built yet —
all six slices are `☐ not done`** (see top status table).

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-06-29 | Initial plan from plane-by-plane audit (399 tests, 89.2% cov). Inputs: Software QA, Software Testing heuristics, software_testing research synthesis. |
| 2026-06-29 | Review fixes (major 1–5): coverage no longer gates `ok` (ST3, amber badge only); `overall.ok = all(plane.ok)` so no green headline over failing planes; mutation kill % reported on Data + Decision (ST3); QA7 security gate (`pip-audit` + `detect-secrets`) added to CI; property-based `hypothesis` suites for optimizer/lot/risk math elevated to st4 P0/P1 (ST6). |
| 2026-06-29 | Added per-plane QA footnote (§4.8): `render_qa_footnote(plane_id)` shows test pass/fail + coverage % on each plane page (`/data`, `/research`, `/decision`, `/execution`, `/reporting`, `/infra`), wired in the dashboard slice and covered by `test_dashboard.py`. |
| 2026-06-29 | Re-sequenced slices: split st4 into **st4 (E2E — up, running, completed; priority)** and **st5 (hard QA — optimizer / analyst/PM / risk property + mutation; END)**. E2E wiring proven first; expensive deep correctness tests deferred to the final slice. |
| 2026-06-29 | Added §4.2.1 synthetic portfolio + IPS builder acceptance items: **structural** (per-SDG-axiom, emit→validate round-trip, cohort coverage, determinism, error-surfacing) gate E2E in st4; **statistical** (distributional checks, null baselines, SDG3 ablation falsifier, 2022–2025 cross-regime) land in st5. Sourced from `research/software_testing.md`; split by cost per Simplicity (S1/S3). |
| 2026-06-29 | **Dashboard moved to top (st0)** for current-phase visibility (dashboard-first): old st2 dashboard → st0 (ships with stub/empty-state), registry → st1, CLI report → st2 (flips panel `stub`→`live`); st3–st5 unchanged. Added top **implementation-status table** and marked **all six slices `☐ not done`** (nothing built yet). |
