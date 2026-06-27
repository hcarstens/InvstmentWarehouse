# Synthetic IPS — Implementation Plan

**Status:** si0a–si4 shipped
**Date:** 2026-06-27
**Owner:** decision plane + research/synthetic
**Inputs:** [`research/synthetic_ips.md`](research/synthetic_ips.md) (design),
[`risk_api_contract.md`](risk_api_contract.md) (boundary + rung lineage),
[`research/hnw_portfolios.md`](research/hnw_portfolios.md) (cohort IPS priors),
[`heuristics/Synthetic Data Generation.md`](heuristics/Synthetic%20Data%20Generation.md) (SDG1–SDG7)

---

## 1. Principle — paired fixtures, decision-plane ownership

HNW research: a test household is **Shape B (portfolio graph) + machine-readable IPS**, not
either alone. The synthetic IPS generator lives in **`warehouse.research.synthetic`** next to
`emit_hnw_fixture`; enforcement lives in **`warehouse.decision`**.

| Layer | Package | Output | Consumer |
| --- | --- | --- | --- |
| **Portfolio generator** *(shipped)* | `research.synthetic` | `HouseholdFixture` (Shape B) + Shape A projection | Risk rung 3–4, optimizer, recon |
| **IPS generator** *(this plan)* | `research.synthetic` | `InvestmentPolicyStatement` co-generated with fixture | Drift monitor, optimizer, workflow smokes |
| **IPS enforcement** | `decision.ips`, `decision.constraints` | Drift report, binding constraints | Dashboard, approval workflow |
| **Risk core** *(unchanged)* | `research.risk` | `RiskResult` on Shape A | Dashboard, HTTP — **no IPS import** |

```text
emit_synthetic_household(cohort, seed, rung)
  → emit_hnw_fixture()           # Shape B + project Shape A  (existing)
  → emit_ips_for_cohort()        # IPS aligned to sampled weights + cohort priors
  → validate_ips(fixture, ips)   # SDG1 — bind or raise
  → seal provenance              # ips_id, stage_hash in ProvenanceManifest
```

**Risk API boundary (contract §5, §6):** `evaluate_risk(request, manifest)` consumes Shape A
only. IPS never crosses into `warehouse.research.risk`. Workflow callers may run risk on the
projected manifest and IPS drift on the same fixture in parallel — the **caller** composes both,
not the risk module.

---

## 2. Scope — what ships vs deferred

### In scope (v1 synthetic IPS)

| Item | Rationale |
| --- | --- |
| Co-generated IPS per cohort + seed | Design brief §A; SDG7 composition |
| `validate_ips(fixture, ips)` | Design brief §C; closes always-feasible falsifier |
| Extend `InvestmentPolicyStatement` (3 constraint fields) | concentration, liquidity floor, turnover |
| Unify `AllocationTarget.asset_class` → `AssetClass` enum | Prerequisite — design brief §B |
| Wire monitor + seed to policy-driven concentration | Remove magic `0.25` in `monitor.py` |
| `emit_synthetic_household()` public API | Single entry for tests + scenario cards |
| Workflow smoke tests (in-process, no DB) | Design brief §D |
| Dashboard panel: synthetic IPS / binding status | Dashboard-first rule |

### Deferred

| Item | Why |
| --- | --- |
| ESG exclusions as IPS fields | Client-specific hard vs soft — design brief open question |
| IPS effective-dating replay engine | Schema exists; replay logic is separate epic |
| `seed_synthetic_household()` DB adapter | Follows risk plan Shape B → DB slice; not blocking in-process smokes |
| Full workflow regression with DB onboarding | After seed adapter |
| Leaf-type priors in rung 3/4 fixtures | Sleeve weights sufficient for IPS v1; leaf harness separate |
| `wealth_source` on IPS JSON | Optional provenance field — add to `ProvenanceManifest` only if needed |

---

## 3. Cohort IPS priors (from hnw_portfolios.md)

IPS targets are derived from **sampled sleeve weights** in the fixture, not independent draws.

| Cohort | Allocation bands | `concentration_limit_pct` | `liquidity_tier_min_pct` (tier 1+2) | Notes |
| --- | --- | --- | --- | --- |
| `general_hnw` | sampled ± 5% headroom | 0.12 | 0.75 | Primary residence out of IPS numerator |
| `uhnw_inherited` | sampled ± 5% | 0.10 | 0.55 | Trust structure; alt calls in fixture |
| `founder_executive` | sampled ± 8% | 0.15–0.45 issuer *of equity sleeve* | 0.70 | Map to portfolio-level cap from issuer metadata |
| `concentrated_stress` | **narrow** bands (±2%) | 0.20–0.25 (must bind vs AAPL lots) | 0.60 | SDG2 — must trigger drift + concentration alerts |

**Binding rule for `concentrated_stress`:** after `validate_ips`, at least one of
{sleeve drift, single-name concentration, liquidity floor} must appear in
`binding_constraints[]`. CI fails if the list is empty.

---

## 4. Migration slices — PR sequence

Apply **SDG3**: accept only when downstream tasks pass (drift non-empty, optimizer binding,
validate raises on bad pairs) — not when JSON looks plausible.

### si0a — asset-class vocabulary + IPS schema *(~1 PR)*

**Goal:** one sleeve enum end-to-end before adding synthetic generation.

| Task | File(s) |
| --- | --- |
| Change `AllocationTarget.asset_class` from `str` to `AssetClass` | `decision/ips/__init__.py` |
| Re-export `AssetClass` from decision IPS or import from `research.risk.models` | `decision/ips/__init__.py` |
| Migrate demo seed targets to 6-sleeve enum | `infra/db/seed.py` |
| Replace `_class_for_ticker` / `"etf"`/`"equity"` drift mapping with sleeve rollup from security master or lot `asset_class` | `decision/ips/monitor.py` |
| Update `row_to_ips` / `save_ips` JSON (de)serialization | `decision/ips/store.py` |
| Fix Phase 3 tests | `tests/test_phase3.py` |

**Acceptance:**

- Demo household drift report uses `AssetClass` sleeve keys matching Shape A projection.
- `pytest tests/test_phase3.py` passes.
- No new imports of `warehouse.research.synthetic` in `decision/`.

**Risk:** demo seed data uses VTI/BND lots — map tickers → `AssetClass.EQUITY` /
`AssetClass.FIXED_INCOME` explicitly in monitor until security-master sleeve lookup exists.

### si0b — policy fields + monitor wiring *(~1 PR)*

**Goal:** concentration, liquidity, turnover on IPS; remove hardcoded cap.

| Task | File(s) |
| --- | --- |
| Add optional fields with defaults: `concentration_limit_pct`, `liquidity_tier_min_pct`, `turnover_budget_pct` | `decision/ips/__init__.py` |
| Persist new fields in `constraints_json` column *(new)* or extend `allocation_json` wrapper | `infra/db/models.py`, Alembic migration, `decision/ips/store.py` |
| Read concentration from IPS in drift monitor | `decision/ips/monitor.py` |
| Add liquidity tier rollup helper on `HouseholdFixture` / lot views | `research/synthetic/liquidity.py` *(new)* or inline in validate |
| Document fields in `constraints.py` `active_constraint_summary` | `decision/constraints.py` |

**Acceptance:**

- Smith demo IPS sets `concentration_limit_pct=Decimal("0.25")`; monitor uses it (not literal).
- `pytest tests/test_frozen.py` if IPS model frozen *(only if we freeze IPS — defer freeze until replay story clear)*.
- Dashboard constraint binding report shows new IPS fields.

### si1 — synthetic IPS generator *(~1 PR)*

**Goal:** cohort-conditioned IPS co-generated with fixture weights.

| Task | File(s) |
| --- | --- |
| `COHORT_IPS_PRIORS` table (concentration, liquidity, band width) | `research/synthetic/ips_cohort.py` *(new)* |
| `emit_ips_for_cohort(cohort_id, seed, household_id, weights) -> InvestmentPolicyStatement` | `research/synthetic/ips_emit.py` *(new)* |
| Build `allocation_targets` from sampled weights ± cohort headroom | same |
| Set `restricted_securities` / sample do-not-sell for rung 4 (optional lot ids) | same |
| Export from `research/synthetic/__init__.py` | `__init__.py` |

**Acceptance:**

- Same `(cohort_id, seed)` → identical IPS (deterministic).
- `concentrated_stress` IPS max equity weight < fixture equity weight OR concentration cap
  < largest issuer weight (at least one binding path exists post-validate).
- Unit tests per cohort; no DB.

### si2 — `validate_ips` + pipeline integration *(~1 PR)*

**Goal:** SDG1 gate before fixture is considered emitted.

| Task | File(s) |
| --- | --- |
| `IpsValidationResult` (`ok`, `binding_constraints`, `warnings`) | `research/synthetic/ips_validate.py` *(new)* |
| `validate_ips(fixture, ips) -> IpsValidationResult` | same |
| Checks: Shape A vs min/max; single-name vs cap; tier 1+2 + unfunded alt vs liquidity floor | same |
| `emit_synthetic_household(cohort, seed, rung) -> SyntheticHouseholdBundle` | `research/synthetic/pipeline.py` |
| Bundle = `{fixture, ips, validation}`; raise `IpsValidationError` on fail | same |
| Optional: call from `emit_hnw_fixture` behind `validate=True` default | `pipeline.py` |

**Acceptance:**

- Valid `(general_hnw, seed=42)` passes; intentionally mismatched IPS raises.
- `concentrated_stress` rung 4: `binding_constraints` non-empty.
- `pytest tests/test_hnw_synthetic.py` extended; new `tests/test_synthetic_ips.py`.

### si3 — workflow smokes + scenario card *(~1 PR)*

**Goal:** SDG3 downstream falsification without DB.

| Task | File(s) |
| --- | --- |
| `run_workflow_smoke(bundle) -> WorkflowSmokeResult` | `research/synthetic/workflow_smoke.py` *(new)* |
| In-process: positions from fixture lots → `build_ips_drift_report` logic (extract pure fn or session-less adapter) | `decision/ips/monitor.py` refactor if needed |
| Optimizer smoke: `run_tax_aware_optimizer` on fixture positions + IPS | reuse `tests/test_phase3.py` patterns |
| Extend `ScenarioCard` with `ips_id`, `binding_constraints_count` | `research/synthetic/scenario_card.py` |
| `build_scenario_card` uses `emit_synthetic_household` | same |

**Acceptance:**

| Workflow | Pass criterion |
| --- | --- |
| policy_monitoring | `concentrated_stress` drift or concentration alerts non-empty |
| rebalance_tax_overlay | optimizer returns ≥0 trades; binding set documentable |
| research_scenario | scenario card fingerprint stable across re-run |

**Note:** refactor `build_ips_drift_report` to accept `InvestmentPolicyStatement` + positions
without `Session` for smoke path — keep DB path as thin wrapper.

### si4 — dashboard + seed adapter *(~1 PR, seed optional flag)*

**Goal:** visible status; optional DB path for demo.

| Task | File(s) |
| --- | --- |
| Panel: synthetic IPS matrix (`cohort × binding status`) on risk/build or phase3 dashboard | `dashboard/render_*.py`, `dashboard/phases.py` |
| `seed_synthetic_household(session, bundle)` — idempotent | `infra/db/seed.py` *(new fn)* |
| CLI or test helper: bootstrap synthetic household by cohort | `tests/test_synthetic_ips_integration.py` |

**Acceptance:**

- `warehouse serve` shows panel with real binding counts from last smoke run (not stub).
- Optional: `seed_synthetic_household` + `pytest` integration test with SQLite.

---

## 5. Public API (target)

```python
# warehouse/research/synthetic/__init__.py

class SyntheticHouseholdBundle(BaseModel):
    fixture: HouseholdFixture
    ips: InvestmentPolicyStatement
    validation: IpsValidationResult

def emit_synthetic_household(
    *,
    cohort_id: str,
    seed: int,
    rung: int = 3,
    household_id: str | None = None,
) -> SyntheticHouseholdBundle: ...

def emit_ips_for_cohort(...) -> InvestmentPolicyStatement: ...
def validate_ips(fixture: HouseholdFixture, ips: InvestmentPolicyStatement) -> IpsValidationResult: ...
```

**Composition with risk (caller-owned):**

```python
bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
manifest = bundle.fixture.asset_portfolio  # Shape A — required non-None after emit
risk = evaluate_risk(RiskRequest(horizon=RiskHorizon.parse("5y")), manifest)
# IPS drift / optimizer use bundle.ips + bundle.fixture.lots — not evaluate_risk
```

---

## 6. SDG acceptance matrix

| Axiom | Criterion | Slice |
| --- | --- | --- |
| SDG1 Fidelity | `validate_ips` pass on every emit; recon NAV unchanged | si2 |
| SDG2 Counterfactuals | `concentrated_stress` binding guaranteed; negation test raises | si2 |
| SDG3 Falsification | Workflow smokes; empty binding fails CI | si3 |
| SDG4 Tensions | `tension_tags` on fixture; IPS headroom ≠ zero for general cohort | si1 |
| SDG5 Provenance | IPS `ips_id` + stage hash in bundle; scenario card links both fingerprints | si3 |
| SDG6 Privacy | Synthetic ids only; no client data | all |
| SDG7 Composition | IPS module replaceable without regenerating lots | si1–si2 |

---

## 7. Dependencies & build order

```text
si0a (AssetClass unify)
  → si0b (IPS policy fields)
    → si1 (emit_ips_for_cohort)
      → si2 (validate_ips + bundle)
        → si3 (workflow smokes)
          → si4 (dashboard + optional DB seed)
```

**Parallel safe:** si0a is independent of risk work. Do **not** start si1 before si0a —
new IPS fields on mismatched sleeve strings inherit the apples-to-oranges bug.

**Risk API:** no changes required to `evaluate_risk` signature. Optional doc-only update to
v1.1 stress table noting IPS bundle as caller-side composition.

---

## 8. Test plan summary

| File | Covers |
| --- | --- |
| `tests/test_synthetic_ips.py` | emit_ips determinism, cohort priors, validate pass/fail |
| `tests/test_hnw_synthetic.py` | extend — bundle NAV + validate on emit |
| `tests/test_synthetic_ips_workflow.py` | smoke matrix per cohort |
| `tests/test_phase3.py` | update for AssetClass + policy-driven concentration |
| `tests/test_synthetic_ips_integration.py` | DB seed path (si4, optional CI job) |

**CI gate:** `concentrated_stress` rung 4 bundle must have `len(validation.binding_constraints) >= 1`.

---

## 9. Self-review (plan quality check)

Reviewed against design brief, risk contract, and codebase 2026-06-27.

### Strengths

- **Respects risk boundary** — IPS stays in decision + synthetic; no `evaluate_risk` signature
  change; mirrors risk plan’s two-layer split.
- **Correct prerequisite ordering** — si0a before si1 matches design brief Gap #4 explicitly.
- **Binding falsifier operationalized** — `concentrated_stress` CI gate makes SDG2/SDG3 testable,
  not aspirational.
- **Incremental PRs** — six slices, each shippable with acceptance criteria; sized like risk v0a/b/c.
- **Dashboard-first** — si4 panel avoids hidden backend-only generator.

### Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Drift monitor ticker→sleeve mapping fragile after si0a | Explicit mapping table in monitor until security master sleeve lookup; test with synthetic fixture tickers |
| `build_ips_drift_report` requires Session | Extract pure `build_ips_drift_report_from_views(positions, ips)` in si3 |
| DB migration for IPS JSON | Add `constraints_json` column; default `{}` for backward compat |
| `emit_hnw_fixture` API break if validate always on | Default `validate=True` on new `emit_synthetic_household`; keep `emit_hnw_fixture` behavior for existing tests until si2 lands |
| Liquidity check needs unfunded alt capital | Sum `alternative_holdings.unfunded_capital` in validate; cite hnw_asset_types falsifier |
| Founder cohort concentration is sleeve-relative | Document conversion: issuer weight / equity sleeve weight → portfolio-level cap for validate |

### Gaps intentionally left open

- IPS version replay when tax law changes mid-year
- ESG as hard ban vs soft penalty
- Minimum drift threshold before realizing gains (optimizer ↔ monitor coordination)
- Whether to freeze `InvestmentPolicyStatement` (wait until replay semantics defined)

### Verdict

Plan is **ready to execute** starting with si0a. Estimated **5–6 PRs**, ~2–3 weeks at current
phase velocity. Critical path: **si0a → si1 → si2**; si3/si4 can overlap after si2 merges.

---

## 10. Doc updates on ship

| Doc | Update |
| --- | --- |
| [`research/synthetic_ips.md`](research/synthetic_ips.md) | Mark sections implemented; link to this plan |
| [`risk_api_contract.md`](risk_api_contract.md) | v1.1 stress table: note caller composes IPS + Shape A |
| [`research/hnw_portfolios.md`](research/hnw_portfolios.md) | Mark `ips.validate()` shipped in pipeline diagram |
| [`TODO.md`](TODO.md) | Close open question #7 (synthetic portfolio stress); add synthetic IPS panel item |
| [`risk_api_implementation_plan.md`](risk_api_implementation_plan.md) | Cross-link Shape B → DB seed dependency on si4 |

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-06-27 | Initial plan from synthetic_ips design brief + risk contract boundary review. Self-review §9 appended before publish. |
