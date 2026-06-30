# QA Plan — Implementation

**Status:** active
**Date:** 2026-06-30
**Owner:** cross-cutting (quality + delivery)
**Inputs:** [`heuristics/Persona of The Software Tester.md`](heuristics/Persona%20of%20The%20Software%20Tester.md),
[`software_testing_implementation.md`](software_testing_implementation.md) (platform — **complete**),
[`CI.md`](../CI.md), [`research/software_testing.md`](research/software_testing.md)

**Baseline (2026-06-30):** testing platform st0–st6 shipped · 601 tests · platform reads
`runs/testing/last_report.json` at `/testing` and per-plane QA footnotes.

---

## 1. Principle — QA runs on the testing platform

The **testing platform is complete** (`software_testing_implementation.md`). This document is
the **QA plan**: how to use that platform to attack the codebase, produce executable evidence,
and ratchet the suite stricter over time.

| Layer | Role in QA |
| --- | --- |
| `testing_registry.py` | Single map: plane → pytest paths → coverage floor → risk tier → property/mutation suites |
| `warehouse test report` | Regenerates evidence artifact (`last_report.json`, `coverage.json`, `e2e_smoke.json`) |
| `/testing` + `GET /api/testing` | Consolidated pass/fail matrix, pyramid mix, E2E smoke headline |
| Per-plane QA footnote | Same artifact on `/data` … `/infra` — no re-run on page view |
| CI `test` job | Full suite + coverage artifact + security gate (`pip-audit`, `detect-secrets`) |
| `warehouse test mutation` | On-demand mutation kill % for Data + Decision (report-only, ST3) |
| `risk_build_registry.py` | Slice-level falsifiers for shipped deliverables |

**Persona stance (¬CT8):** QA does not steel-man features. It weak-point hunts running code
with independent oracles (ST2), concentrates budget at boundaries and tail-risk paths (ST6,
QA3, RM5), and treats a green bar as “no counterexample found *yet*” (ST1).

**Coverage is not quality (¬QA6):** line % on `/testing` is an amber gap-finder badge only.
Discriminating power comes from **mutation kill %** (Data, Decision) and **property-based
invariants** (`hypothesis` on lot, optimizer, risk math).

---

## 2. Tester axioms → QA obligations

| Axiom | QA obligation in this repo |
| --- | --- |
| **ST1 Adversarial falsification** | Every QA pass includes at least one hostile input per touched module; happy-path-only PRs are incomplete |
| **ST2 Oracle** | Expected values from spec, hand math, or invariant — never copied from current output without justification |
| **ST6 Boundaries** | Empty portfolio, zero NAV, max concentration, wash window, 364/365-day holding period, malformed CSV |
| **ST5 Determinism** | Seeded RNG (`hypothesis` derandomize profile); session SQLite; zero flake tolerance — quarantine = P1 |
| **ST4 Pyramid** | Verify at cheapest level first; E2E smoke (4/4 cohorts) is thin top, not the main gate |
| **QA3 Risk-weighted budget** | Data + Decision get deepest scrutiny; Reporting gaps declared explicitly |
| **ST8 Regression ratchet** | Bug fix workflow: failing test → fix → green; register path in `testing_registry.py` if new plane coverage |
| **QA7 Security** | `pip-audit` + `detect-secrets` must pass on every PR — same bar as functional tests |

**8-point checklist** (from Mental Model of The Software Tester): score each major deliverable
PR against oracle, adversarial inputs, boundaries, determinism, pyramid/latency, risk budget,
mutation adequacy (critical planes), and regression capture. Target **≥6/8** before ship;
**8/8** for critical-plane changes (ledger, optimizer, tax).

---

## 3. Platform commands — when to run what

### 3.1 Every commit (local, &lt; 2 min target for touched area)

```bash
# Canonical gate — mirror CI
ruff check src tests && ruff format --check src tests && mypy src/warehouse && pytest

# Plane-scoped (from testing_registry.py pytest_paths)
pytest tests/test_phase2.py -q   # example: touched execution/recon
```

### 3.2 Before opening PR (~full suite, ~5–15 min)

```bash
warehouse test report
```

Writes `runs/testing/last_report.json` + `coverage.json` + `e2e_smoke.json`. Verify:

- `overall.ok` is true (all plane `failed == 0` and E2E smoke 4/4)
- No plane row red on `/testing`
- Coverage below floor → amber only; note in PR if intentional

Optional local dashboard check:

```bash
warehouse serve   # separate terminal
curl -s http://127.0.0.1:8765/api/testing | python -m json.tool
```

### 3.3 Weekly / pre-release (critical planes)

```bash
warehouse test report --mutation   # or: warehouse test mutation && warehouse test report
```

Review mutation kill % on Data (`lot_ledger`) and Decision (`optimizer/qp.py`). Rising or
stalled kill % → add assertions or property tests before next feature work on that module.

### 3.4 CI (automatic on every PR)

Same as §3.2 plus security gates — see `CI.md` § Security gates. Artifacts retained 7 days.

**Flake quarantine protocol (ST5):** Any test that returns a different verdict on the same
commit on two CI runs must be quarantined immediately — mark
`@pytest.mark.skip(reason="FLAKY: <description>")` or move to `tests/quarantine/` — and
logged in `JOURNAL.md` as a P1 suite defect. A quarantined test blocks the next release
until fixed or deleted. Never train the team to ignore red.

### 3.5 Deliverable ship (track falsifier)

Before marking a `risk_build_registry.py` row `shipped`:

```bash
pytest <falsifier_test> -q   # must be green
pytest tests/test_testing_registry.py -q   # registry still complete
```

---

## 4. QA workflows

### 4.1 Shift-left — feature PR

```text
1. Identify plane(s) in testing_registry.py
2. State oracle before coding the test (ST2)
3. Add unit/property test at cheapest level (ST4)
4. Run plane pytest_paths subset + full CI gate
5. Refresh artifact: warehouse test report
6. Confirm QA footnote on affected plane page (test_dashboard.py pattern)
7. If new frozen type → FROZEN_TYPES + test_frozen.py
```

### 4.2 Bug fix — regression ratchet (ST8)

```text
1. Reproduce with a failing test (red)
2. Fix code (green)
3. If gap was a missing boundary class → extend property suite or §6 hunt list
4. Log escape in JOURNAL.md (defect escape rate manual until tooling)
5. warehouse test report — confirm plane row still ok
```

### 4.3 Exploratory charter (manual, per release)

Time-boxed **weak-point hunt** (¬CT8) after automated suite is green. Not a substitute for
automated tests — feeds the next regression tests.

| Session | Focus | Seed scenarios |
| --- | --- | --- |
| **E1 Data ingest** | Malformed custodian files, duplicate lots, stale `as_of_date` | Empty CSV, wrong columns, future dates, qty overflow |
| **E2 Recon / refresh** | Break taxonomy visibility on dashboard | Force break → confirm exception queue + `/execution` panel |
| **E3 Optimizer** | Infeasible IPS, singular Σ, all constraints binding | Zero NAV, single-asset book, max turnover = 0 |
| **E4 Risk / synthetic** | Lookahead, SDG axiom violations | Walk-forward purge boundary, cohort with conflicting sleeves |
| **E5 Reporting / tax** | Cliff thresholds, character splits | NIIT boundary income, 364 vs 365-day lots |
| **E6 Dashboard** | Stale artifact, missing report | Delete `last_report.json`, confirm empty-state + footnote |

Record findings as pytest falsifiers; do not close exploratory session without filing tests or
explicit backlog rows in §7. Log every completed session in **§4.5**.

### 4.4 Release readiness checklist

| # | Check | Pass |
| --- | --- | --- |
| 1 | `warehouse test report` → `overall.ok` | true |
| 2 | E2E smoke | 4/4 households |
| 3 | Pyramid actual vs 70/25/5 | No E2E inversion (E2E &gt; 10%) |
| 4 | Security gate | 0 high/critical vulns, 0 new secrets |
| 5 | `git_sha` in artifact matches `HEAD` | not stale on dashboard |
| 6 | Critical-plane mutation (if run) | kill % not regressing &gt; 5 pts |
| 7 | §7 P1 gaps | None blocking release scope |
| 8 | Exploratory session E* for touched planes | Logged in §4.5 or waived with reason |
| 9 | Oracle review (ST2) | Each new test's expected value traces to spec/hand-math/invariant — reviewer confirms, not inferred from code output |
| 10 | Flake quarantine | Zero unresolved quarantine-tagged tests on `main` |

### 4.5 Exploratory session log

Every completed session must be recorded here before the release is marked ready (§4.4 #8).
A waived session requires an explicit reason. Do not leave this table empty across a release.

| Date | Session | Scope / planes | Findings | Outcome |
| --- | --- | --- | --- | --- |
| _(none yet — run before first release)_ | | | | |

---

## 5. Per-plane QA matrix

Commands are the union of `pytest_paths` + `property_paths` from
`src/warehouse/dashboard/testing_registry.py`.

> **Primary quality signal — critical planes:** mutation kill % (Data, Decision), not
> coverage %. Coverage floors listed below are amber gap-finder **badges only** — hitting
> the floor number does not mean the plane is adequately tested.

### 5.1 Data — `critical` · mutation reported · floor 90% (badge)

**Blast radius:** Wrong lots or symbology poison every downstream plane.

| QA focus | Oracle | Automated suite | Weak-point hunts (§6) |
| --- | --- | --- | --- |
| Entity graph | Known topology | `test_phase1.py`, `test_architecture.py` | Beneficiary edges |
| Security master | Tax character, wash groups | `test_architecture.py` | Corporate actions |
| Lot ledger | qty × basis, holding period | `test_phase2.py`, `test_lot_properties.py` | Wash-sale chain merge |
| Ingest | Parsed rows → positions | `test_phase2.py` | Malformed file → surfaced error |

```bash
pytest tests/test_phase1.py tests/test_phase2.py tests/test_architecture.py \
  tests/test_lot_properties.py -q
```

### 5.2 Research — `high` · floor 93% (badge)

**Blast radius:** Lookahead, wrong risk numbers, synthetic fixtures that do not stress bindings.

| QA focus | Oracle | Automated suite |
| --- | --- | --- |
| Risk API v0/v1 | Contract envelopes | `tests/test_risk_*.py` |
| Risk math (property) | VaR ≤ CVaR, corr bounds, sub-additivity | `test_risk_properties.py` |
| HNW synthetic / IPS | SDG axioms, emit→validate | `test_hnw_synthetic.py`, `test_synthetic_ips*.py` |
| Statistical paths | Distributional + null + ablation + cross-regime | `test_synth_*.py` |
| E2E smoke | Independent legs per cohort | `test_end_to_end_synthetic.py`, `test_e2e_smoke.py` |

```bash
pytest tests/test_risk_*.py tests/test_hnw_synthetic.py tests/test_synthetic_ips*.py \
  tests/test_ips_*.py tests/test_synth_*.py \
  tests/integration/test_end_to_end_synthetic.py tests/test_e2e_smoke.py -q
```

### 5.3 Decision — `critical` · mutation reported · floor 93% (badge)

**Blast radius:** Wrong weights, silent constraint violations, tax seams, gates bypassed.

| QA focus | Oracle | Automated suite |
| --- | --- | --- |
| IPS monitor | Drift vs IPS | `test_phase3.py` |
| Optimizer v1 | QP KKT, turnover, robust stress | `test_optimizer_*.py` |
| Optimizer (property) | Σw=1, long-only, turnover ≤ bound, monotone risk-aversion | `test_optimizer_properties.py` |
| Tax overlay | Tax delta vs baseline | `test_optimizer_tax_seam.py` |
| PM / analyst | Narrative, NPA, attribution | `test_pm_*.py`, `test_analyst_*.py` |
| Orchestrator | Office Manager gate | `test_orchestrator.py` |

```bash
pytest tests/test_phase3.py tests/test_optimizer_*.py tests/test_pm_*.py \
  tests/test_analyst_*.py tests/test_orchestrator.py -q
```

### 5.4 Execution — `high` · floor 90% (badge)

**Blast radius:** Staged orders without recon truth; post-trade breaks invisible.

```bash
pytest tests/test_phase2.py tests/test_phase4.py -q
```

**Declared gaps (QA3):** multi-custodian break taxonomy; OMS cancel/replace boundaries.

### 5.5 Reporting — `medium` · floor 80% (badge)

**Blast radius:** Tax and performance reports wrong with no tests.

```bash
pytest tests/test_reporting_performance.py tests/test_reporting_tax.py \
  tests/test_report_writer.py -q
```

**Declared gaps:** after-tax return YTD (`after_tax_return_ytd`); decision estimator seam (po1-tax).

### 5.6 Infrastructure — `medium` · floor 85% (badge)

```bash
pytest tests/test_infra_health.py tests/test_config.py tests/test_frozen.py -q
```

**Declared gaps:** Postgres/Redis (Phase 5); migration rollback.

### 5.7 Cross-cutting — `medium` · floor 80% (badge)

```bash
pytest tests/test_messaging_*.py tests/test_architecture.py tests/test_dashboard.py \
  tests/test_risk_build_dashboard.py tests/integration/test_end_to_end_synthetic.py -q
```

Dashboard QA falsifiers:

```bash
pytest tests/test_dashboard.py -k "testing or qa_footnote" -q
```

---

## 6. Adversarial hunt catalog (tail-weighted)

Prioritized inputs to try when extending tests or running exploratory sessions. Aligns with
**tail-failure minimization** (¬RM4) — over-invest in low-probability, high-consequence paths.

| ID | Plane | Hostile input | Expected behavior | Target module / test | Attempted | Falsifier filed |
| --- | --- | --- | --- | --- | --- | --- |
| **H1** | Data | Empty ingest file | Raised / surfaced error, not silent empty book | `test_phase2.py` | | |
| **H2** | Data | Wash-sale window overlap on partial lot sell | Correct basis adjustment | `test_lot_properties.py` extension | | |
| **H3** | Data | `as_of_date` stale vs ledger marks | Recon break opened | `test_phase2.py` | | |
| **H4** | Execution | Order cancel after partial fill | State machine consistent | `test_phase4.py` extension | | |
| **H5** | Execution | Multi-custodian same ISIN, different symbology | Break typed, not merged away | backlog qa1 | | |
| **H6** | Decision | Near-singular covariance matrix | Raises or documented fallback | `test_optimizer_properties.py` | | |
| **H7** | Decision | All constraints binding simultaneously | Feasibility or explicit infeasible | `test_optimizer_qp.py` | | |
| **H8** | Decision | IPS max concentration = current weight | No spurious trade | `test_phase3.py` | | |
| **H9** | Research | Scenario with future data in purge window | `WalkForwardError` | `test_phase3.py` extension | | |
| **H10** | Research | SDG-disabled generator | Worse downstream pass rate vs full | `test_synth_sdg_ablation.py` | ☑ | ☑ |
| **H11** | Reporting | 364-day lot → STCG, 365-day → LTCG | Correct character | `test_reporting_tax.py` | ☑ | ☑ |
| **H12** | Reporting | Missing price mark on performance path | Loud failure, not zero return | `test_reporting_performance.py` | | |
| **H13** | Infra | Mutate frozen settings in place | `FrozenInstanceError` | `test_frozen.py` | | |
| **H14** | Cross | Concurrent messaging handlers | Deterministic ordering / isolation | `test_messaging_*.py` | | |

**H-ID completion protocol:** Before closing any exploratory session (§4.3), mark
`Attempted` ☑ for each H-ID tried. File a falsifier test (or add to §7 backlog) and mark
`Falsifier filed` ☑. Hunts without ☑ in both columns are open gaps — name them in the
session log (§4.5), do not silently skip them.

---

## 7. Gap backlog → QA implementation slices

Remaining gaps from `software_testing_implementation.md` §4 P1, reframed as **QA work** using
the existing platform (registry update + falsifier + footnote verification).

| Priority | Slice | Plane | Gap | Acceptance | Falsifier |
| --- | --- | --- | --- | --- | --- |
| **P1** | **qa3** | Data | Wash-sale chain under random lot streams | Property test extension; invariant stated before writing test | `test_lot_properties.py` |
| **P1** | **qa5** | Decision | Near-singular Σ; all-constraints-binding | Property / QP edge cases; raises or explicit infeasible | `test_optimizer_properties.py` |
| **P1** | **qa7** | Reporting | After-tax return YTD | Independent oracle (hand-math vs events table) — client-facing metric, Decision-tier blast radius | `test_reporting_performance.py` |
| **P1** | **qa1** | Execution | Multi-custodian break taxonomy | Each break type has oracle + dashboard visibility | `test_phase4.py` + registry note |
| **P2** | **qa2** | Execution | OMS cancel/replace boundaries | State transitions asserted | `test_phase4.py` |
| **P2** | **qa4** | Data | Corporate actions on lot ledger | Independent basis oracle | `test_phase2.py` or new module test |
| **P2** | **qa6** | Research | Explicit `WalkForwardError` expansion | Future-data injection raises | `test_phase3.py` or risk workflow test |
| **P2** | **qa8** | Data | Beneficiary graph edges | Graph oracle | `test_phase1.py` |

**qa7 note:** `after_tax_return_ytd` is the primary client-facing performance metric. A
wrong value here reaches the client directly. Although Reporting is classified `medium`
plane, this gap carries Decision-tier blast radius and is P1 regardless of plane tier.

**Slice protocol:** red test → green fix → `warehouse test report` → confirm plane footnote →
update `testing_registry.py` `note` if scope changes → mark shipped in PR description.

---

## 8. Metrics — read from the platform

Do not maintain a parallel spreadsheet. Primary sources:

| Metric | Source | QA action |
| --- | --- | --- |
| Pass rate | `overall.passed / overall.tests` | Must be 100% on `main` |
| Per-plane pass/fail | `planes[].ok` | Red row blocks release |
| Coverage % vs floor | `coverage_status` | Amber → schedule gap closure; never sole quality signal |
| Mutation kill % | Data + Decision rows | **Run establishing baseline before weekly cadence begins** — record in `runs/testing/history.jsonl`; trend review weekly; &lt; 70% → qa slice |
| Pyramid mix | `pyramid` vs `PYRAMID_TARGET` | Alarm if E2E &gt; 10% |
| E2E smoke | `e2e_smoke.passed / households` | Must be 4/4 |
| Stale artifact | `stale: true` | Run `warehouse test report` |
| Security | CI security step | Zero high/critical, zero new secrets |
| Defect escape | `JOURNAL.md` manual | Each escape → ST8 test + journal line |
| CI duration | Actions timing | Target &lt; 15 min; split only if sustained breach |

Append snapshot to `runs/testing/history.jsonl` on release tags (optional, gitignored).

---

## 9. Ownership and registry hygiene

| Action | Owner | Registry touch |
| --- | --- | --- |
| New plane module | Feature PR author | Add `pytest_paths` if new test file |
| New property suite | QA-heavy PR | `property_paths` on plane row |
| New critical math module | Decision/Data author | Consider `report_mutation` target |
| Shipped deliverable | Track owner | `risk_build_registry.py` `falsifier_test` |
| Exploratory finding | Session lead | §7 backlog row or immediate falsifier |

**Invariant:** `pytest tests/test_testing_registry.py` — every `status.PLANES` entry maps to a
registry slice; all `pytest_paths` exist on disk.

---

## 10. Test authoring rules (QA gate on review)

| Rule | Source | Enforcement |
| --- | --- | --- |
| Oracle documented in test name or docstring | ST2 | Reviewer confirms |
| Expected value traces to spec/hand-math/invariant — never copied from code output | ST2 | Reviewer confirms; §4.4 #9 release check |
| No `except: pass` in tests or code under test | CLAUDE.md | `ruff` / reviewer |
| Property tests use `hypothesis` settings profile from `conftest.py` | ST5 + ST6 | Reviewer confirms |
| No network in unit tests | ST5 | Reviewer confirms |
| Bug fixes include regression test in same PR | ST8 | Reviewer confirms |
| New flake → quarantine immediately, log in `JOURNAL.md` | ST5 | §4.4 #10 release check |
| Dashboard failures must be visible — ingest/recon/optimizer errors in panels | CLAUDE.md | Reviewer confirms |
| Walk-forward unsafe code must raise, not clip | CLAUDE.md | Reviewer confirms |

---

## 11. Self-review

### Strengths

- **Platform-complete** — QA executes against live dashboard + CI artifacts, not a paper plan.
- **Persona-grounded** — adversarial, oracle-first, coverage-skeptical, tail-weighted.
- **Plane-aligned** — matches operational planes stakeholders see at `warehouse serve`.
- **Explicit gaps** — silent under-testing avoided (QA3); §7 backlog is visible.

### Risks

| Risk | Mitigation |
| --- | --- |
| Exploratory sessions skipped under deadline | Minimum E* session per release checklist §4.4 |
| Mutation run skipped (slow) | Weekly calendar trigger; `--mutation` before Decision/Data releases |
| Coverage amber ignored | Pair with mutation kill % on critical planes |
| Adversarial hunts filed as “won’t fix” | Require “input never received” justification per persona blind-spot note |

### Verdict

The testing platform provides the **instrument**; this plan provides the **procedure**. Execute
§3 commands on every PR, §4 workflows by change type, §5–§6 for plane depth, and §7 slices to
close the documented gap backlog. A green CI bar plus green `/testing` matrix is necessary but
not sufficient — confidence scales with hostile inputs tried (ST1) and gaps explicitly closed
(ST8).

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-06-30 | Initial QA plan — platform complete (st0–st6); persona axioms; per-plane matrix from `testing_registry.py`; gap backlog qa1–qa8; exploratory charter E1–E6; adversarial hunt catalog H1–H14. |
| 2026-06-30 | Fixes 1–8 from persona review: H-ID hunt tracking columns + completion protocol; flake quarantine protocol + CI spec (§3.4); §4.5 exploratory session log; release checklist adds oracle-trace (#9) and quarantine (#10) checks; §5 callout demotes coverage floors, headers reordered; §7 priority column (qa3/qa5/qa7/qa1 = P1); qa7 escalated to P1 with blast-radius note; mutation baseline requirement added to §8; §10 enforcement column added with oracle-trace rule. |
