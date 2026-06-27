# Synthetic IPS — design brief

Research synthesis for a **synthetic IPS generator** paired with the compositional
HNW portfolio generator and the six core workflows. Consolidates findings from
[ips.md](ips.md), [hnw_asset_types.md](hnw_asset_types.md), and
[portfolio_optimization.md](portfolio_optimization.md) against current
`warehouse.research.synthetic` and `warehouse.decision` implementation.

**Related:** [hnw_portfolios.md](hnw_portfolios.md),
[risk_api_contract.md](../risk_api_contract.md),
[Synthetic Data Generation](../heuristics/Synthetic%20Data%20Generation.md),
[risk_api_implementation_plan.md](../risk_api_implementation_plan.md),
[ips.md](ips.md)

---

## Document roles (how the three inputs fit)

| Doc | Primary job | Credence | Best for |
| --- | --- | --- | --- |
| [ips.md](ips.md) | Governance: hard/soft constraints, drift → optimizer → approval | 0.46 | Synthetic IPS design, constraint library, workflow gates |
| [hnw_asset_types.md](hnw_asset_types.md) | What HNW books hold (A–O), cohort ordering, platform mapping | 0.89 | Leaf taxonomy, ingest priority, liquidity tiers |
| [portfolio_optimization.md](portfolio_optimization.md) | Math: **w**, **Δw**, **Σ**, solver tiers, after-tax MIQP | 0.70 | Optimizer upgrade path, risk-budget vs weight rebalance |

Intended pipeline across all three:

```text
cohort + wealth_source  →  synthetic portfolio (Shape B)
                       →  synthetic IPS (binding, not always-feasible)
                       →  daily_refresh / policy_monitoring
                       →  tax-aware optimizer
                       →  approval → execution
```

---

## What is implemented today

### Synthetic portfolio generator — largely shipped

`warehouse.research.synthetic` implements much of [hnw_portfolios.md](hnw_portfolios.md):

- 15 leaf types (A–O) in `hnw_asset_types.py`, aligned with the taxonomy table
- Cohort-conditioned sleeve priors (`general_hnw`, `uhnw_inherited`,
  `founder_executive`, `concentrated_stress`)
- Shape B fixtures (lots, alts, calls) at rung 3–4 via `emit_hnw_fixture`
- Shape A projection for risk API; combinatorial stress harness
- SDG5 provenance (`generator_version`, `stage_hashes`, `tension_tags`)

**Lineage (one ground truth, two layers):** the risk module's `risk.synthetic.rung()`
ladder is the single ground-truth entry point — rungs 0–2 are hand-built simple manifests;
**rungs 3–4 delegate to `emit_hnw_fixture`** and project Shape B → Shape A. This HNW
generator is the high-complexity backing for `rung()`, not a parallel system. See
[risk_api_contract.md](../risk_api_contract.md) §5.

### Synthetic IPS generator — not shipped

There is no `emit_ips_fixture` or cohort-paired IPS generation. IPS today is:

- A Pydantic model carrying `ips_id`, `household_id`, `version`, `effective_date`,
  `allocation_targets` (min/max/target), and `restricted_securities` — versioning and
  effective-dating scaffolding **already exist**; replay/enforcement logic does not
- One hand-seeded demo policy in `seed.py` (Smith household)
- Concentration is enforced as a **hardcoded `0.25`** in `decision/ips/monitor.py`,
  divorced from IPS — not a "missing expected field" but a magic constant the policy
  cannot set. `constraints.py` references none of concentration/liquidity/turnover;
  liquidity floors and turnover budget are absent entirely. So a synthetic IPS generator
  has no schema to target, and the concentration cap cannot be cohort-conditioned

### Workflows — catalog exists; synthetic end-to-end path incomplete

`warehouse.workflows.catalog` defines onboarding through alternatives. Onboarding
outputs `machine_readable_ips`, but nothing generates IPS synthetically for test
households. The governance pipeline in [ips.md](ips.md) is conceptually wired;
the **fixture pair (portfolio + IPS) for workflow regression is missing**.

---

## Cross-doc strengths

1. **Shared failure-mode vocabulary** — All three echo the same falsifiers:
   prose-only IPS, weight-only books, always-feasible IPS, optimizer-before-reconciliation.
   That matches SDG3 (downstream falsification) and is the right bar for synthetic data.

2. **`hnw_asset_types.md` ↔ code is the tightest link** — The A–O table, IPS
   exclusion of N/O, sleeve rollup, and liquidity tiers are implemented in
   `HnwAssetSpec` / `IpsExcludedError`. Combinatorial harness directly exercises
   doc claims.

3. **`ips.md` governance pipeline matches Phase 3 architecture** — Drift monitor →
   asset location → TLH/heuristic optimizer → explainable trades → approval is what
   `decision/ips/monitor.py`, `optimizer/heuristics.py`, and approval workflow
   implement.

4. **`portfolio_optimization.md` honestly scopes v0** — Documents TLH + greedy
   rebalance, not full MV QP; notes risk plane computes `w'Σw` while decision plane
   does not yet solve constrained QP.

---

## Gaps and inconsistencies

### 1. Pipeline stage `ips.validate()` is documented but absent

[hnw_portfolios.md](hnw_portfolios.md) specifies:

```text
→ ips.validate()         # project to feasible polytope
```

`emit_hnw_fixture` stops at reconciliation (lot NAV + alt NAV) and Shape A projection.
No step ensures the emitted book **binds** against a synthetic IPS — the
“always-feasible IPS” falsifier from all three docs remains untested.

### 2. Cohort models do not fully match

| Doc says | Code does |
| --- | --- |
| 3 wealth-source cohorts with leaf-type rank ordering | 4 cohorts on **6-sleeve** `AssetClass` weights only |
| `wealth_source: founder\|inherited\|executive\|general` in IPS JSON (open question) | Not in cohort IDs or fixture provenance |
| 15 leaf types drive portfolio composition | Leaf types used in combinatorial harness; rung 3/4 fixtures use sleeve weights, not leaf priors |

`hnw_asset_types.md` cohort tables (Cohort 1/2/3) inform **ingest priority**, not yet
**generation priors** beyond sleeve ranges.

### 3. IPS model narrower than research docs

Docs enumerate: concentration caps, liquidity floors, turnover budget, do-not-sell lots,
wash-sale graph, ESG exclusions, drift bands, hard stops (never buy structural drawdown).

`InvestmentPolicyStatement` today carries `ips_id`, `household_id`, `version`,
`effective_date`, `allocation_targets`, and `restricted_securities`. Wash-sale and
do-not-sell are enforced at **lot** level in `constraints.py`, not emitted from a
synthetic IPS. Concentration is a hardcoded `0.25` in `monitor.py` (not policy-driven);
liquidity and turnover are described in docs but absent as fields — so a synthetic IPS
generator has no schema to target. Note the versioning/effective-dating fields already
exist; that gap is **replay logic, not schema**.

### 4. Asset-class vocabulary mismatch

- Demo seed IPS uses `etf` / `equity` string classes
- Risk/synthetic uses `AssetClass` enum (6 sleeves)
- [hnw_asset_types.md](hnw_asset_types.md) asks: 6 sleeves vs 15 leaf types for
  optimizer constraints?

Until this is unified, synthetic portfolio → IPS drift → optimizer can compare
apples to oranges.

### 5. DHA appendix duplication

Base rates about workflows, InvestmentWarehouse, tax-aware optimization, and
dashboard-first appear in all three input docs. Fine for DHA provenance; noisy for
maintainers. Consider a shared appendix or collapsing repeated falsifiers on sync.

### 6. Low credence on IPS governance (0.46) vs high on asset types (0.89)

[ips.md](ips.md) correctly flags uncertainty (ESG hard vs soft, asymmetric drift
bands, estate vs IPS conflict). A synthetic IPS generator should **encode these as
tension tags** (SDG4) rather than picking one interpretation — e.g.
`esg_mode: hard|soft`, `estate_step_up_priority: bool`.

---

## Recommendations

### A. Co-generate IPS with portfolio cohort (SDG7)

Do not draw IPS independently of the book. Cohort profile should emit both:

```text
emit_hnw_fixture(cohort, seed) → HouseholdFixture
emit_ips_for_cohort(cohort, seed) → InvestmentPolicyStatement
  # min/max aligned to sampled weights ± drift headroom
  # concentrated_stress: tight single-name cap that WILL bind
```

`concentrated_stress` must emit a **binding** IPS (tight single-name cap, narrow
sleeve bands). Workflow smoke tests **fail** when no constraint binds — guarding
against the “always-feasible IPS” falsifier.

### B. Extend `InvestmentPolicyStatement` minimally for v1 synthetic

**Prerequisite — unify the asset-class vocabulary first (Gap #4):** make
`AllocationTarget.asset_class` the 6-sleeve `AssetClass` enum (seed uses `"etf"`/`"equity"`
strings today). Adding the fields below before this unification makes them inherit the
apples-to-oranges mismatch.

Priority fields from the three input docs, in binding order:

1. `concentration_limit_pct` (single-name)
2. `liquidity_tier_min_pct` (tier 1+2 floor)
3. `turnover_budget_pct` (annual)
4. `do_not_sell_lot_ids` / `restricted_securities` (already partial)
5. Defer ESG to soft penalty until client-specific interpretation is resolved
   ([ips.md](ips.md) leading uncertainty)

### C. Implement `ips.validate(fixture, ips)`

Before sealing provenance:

- Project Shape A weights vs IPS min/max
- Check liquidity ladder vs tier floors (include unfunded alt commitments —
  falsifier in [hnw_asset_types.md](hnw_asset_types.md))
- Return `binding_constraints[]` for SDG1 acceptance

### D. Workflow regression matrix

| Workflow | Synthetic inputs | Pass criterion |
| --- | --- | --- |
| onboarding | fixture + IPS | machine-readable IPS stored, graph coherent |
| daily_refresh | fixture lots | recon balanced |
| policy_monitoring | fixture + IPS | drift report non-empty for `concentrated_stress` |
| rebalance_tax_overlay | fixture + IPS + lots | optimizer produces trades; binding report non-empty |
| research_scenario | scenario card | optimizer inputs fingerprint stable |

This is the SDG3 bar all three input docs advocate — not KS tests on weights.

### E. Doc cross-links

- [ips.md](ips.md) → link [hnw_portfolios.md](hnw_portfolios.md) (axioms),
  [portfolio_optimization.md](portfolio_optimization.md) (objective hierarchy)
- [hnw_asset_types.md](hnw_asset_types.md) → note leaf harness vs rung fixture
  distinction
- [portfolio_optimization.md](portfolio_optimization.md) → link IPS hard-constraint
  table; state current v0 = heuristics not QP

---

## Bottom line

| Area | Doc quality | Code alignment | Next step |
| --- | --- | --- | --- |
| HNW asset taxonomy | Strong (0.89) | **Good** — enum + harness | Wire leaf priors into rung 3/4 if leaf-level realism matters |
| Portfolio optimization theory | Strong (0.70) | **Partial** — risk Σ yes, MV optimizer no | Keep doc as upgrade spec; do not over-promise in dashboards |
| IPS governance | Strong content, low credence (0.46) | **Weak** — constraint fields + generator missing; versioning scaffold exists | **Synthetic IPS generator paired to cohort** is the critical path |
| Workflows | Consistent across docs | **Catalog only** | End-to-end synthetic household drives onboarding → rebalance smoke |

The research trilogy is **directionally correct and internally consistent** on the
north star (after-tax utility inside IPS bounds, lot-level books, downstream
falsification). The main engineering debt is the **missing synthetic IPS layer** and
the **`ips.validate()` bridge** between portfolio generator and optimizer/workflow
tests — without those, demos pass on weight-only, always-feasible books and fail in
pilot.

---

## Open sub-questions

- Standard schema for IPS constraint objects (weights, concentration, liquidity,
  exclusions) across custodians and optimizers?
- IPS version effective-dating and replay when tax law or mandate changes mid-year?
- Publish `wealth_source` in synthetic IPS JSON to pick default asset-type prior?
- Which workflows are in-scope for v1 pilot — full rebalance or opportunistic TLH only?
- Minimum IPS drift threshold to justify realizing gains on run-up sleeve — optimizer
  vs drift monitor coordination?
- IPS hard stop: never rebalance into single-name drawdown below X% of portfolio?
