# What defines an HNW portfolio for wealth management—and how should synthetic portfolios be generated?

Research brief for building an InvestmentWarehouse **synthetic portfolio generator**:
portfolio structure axioms, cohort profiles, compositional pipeline, rung ladder, and
SDG acceptance tests.

**Related:** [hnw_asset_types.md](hnw_asset_types.md),
[Synthetic Data Generation](../heuristics/Synthetic%20Data%20Generation.md),
[risk_api_contract.md](../risk_api_contract.md),
[risk_api_implementation_plan.md](../risk_api_implementation_plan.md)

**Research run:** `runs/research/hnw-portfolios-2026/20260626T120000Z0000/`
(quality score 10/10, credence 0.89)

**Config:** `configs/research_agents/hnw_portfolios_20260626.json`

Run status: `complete`

Research quality score: `10/10`

## Bottom Line

Synthesis for 'What defines an HNW portfolio for wealth management—and how should synthetic portfolios be generated for InvestmentWarehouse testing?': 102 supporting claim(s), 28 disconfirming claim(s); deterministic credence 0.892. 14 open sub-question(s) recorded.

An HNW portfolio is **not a weight vector** — it is a household-scoped property graph
with lot-level ledger, IPS constraints, and liquidity tiers. The generator must be
**compositional** (SDG7), **axiom-first** (SDG1), and validated by **downstream tasks**
(risk API, optimizer, reconciliation) — not by how realistic the weights look (SDG3).

---

## Portfolio Structure Axioms

| Axiom | Rule | Generator implication |
| --- | --- | --- |
| Graph | Household → entities → accounts → lots → instruments | Emit graph-coherent fixtures, not weights alone |
| IPS scope | Investable numerator excludes primary residence & personal-use | Tag `ips_scope: investable \| total_balance_sheet` |
| Lots | Taxable positions have qty, basis, acquisition date | Required for TLH / after-tax optimizer tests |
| Concentration | Single-name 5–40% common (founder cohort) | Issuer-level metadata, not sleeve-only |
| Multi-account | 2–5 accounts (taxable, IRA, Roth, trust) | Asset-location pairing across accounts |
| Alts sub-ledger | vintage, committed, unfunded, call dates | Weight-only alt sleeve insufficient for liquidity stress |
| Reconciliation | Σ lot MV = account NAV; Σ accounts = household IPS NAV | Validate before emit |
| Mark cadence | Tier-1 daily, Tier-2 monthly, Tier-3 quarterly/event | Timestamp marks per liquidity tier |

**Portfolio layers (outside-in):**

```text
Household
  └── Entity (Person, Trust, LLC)
        └── Account (taxable, IRA, Roth, 401k)
              └── Lot (instrument × qty × basis × date)
                    └── Instrument (security master: class, tax_character, liquidity_tier)
```

---

## Compositional Generator Pipeline (SDG7)

```text
cohort.sample()
  → graph.build()          # entities + accounts
  → sleeves.allocate()     # AssetClass weights, cohort-conditioned
  → lots.split()           # lot ledger per account
  → alts.schedule_calls()  # PE/VC call calendar
  → ips.validate()         # project to feasible polytope
  → manifest.seal()        # provenance (SDG5)
```

Each stage is independently testable and replaceable. Failures localize to the stage
(e.g. replace `lots.split()` without regenerating `graph.build()`).

### SDG acceptance tests

| Axiom | Acceptance criterion |
| --- | --- |
| SDG1 Fidelity | `ips.validate()` + `recon.balance()` pass on every emit |
| SDG2 Counterfactuals | Named negation scenarios (`negate_liquidity_floor`, `negate_concentration_cap`, `negate_lot_granularity`) with deterministic seeds |
| SDG3 Falsification | Risk rung regression + optimizer smoke + recon queue empty — not KS tests on weights |
| SDG4 Tensions | Base case preserves ≥1 tension (`tension_tags[]` in manifest) |
| SDG5 Provenance | Every weight/lot traces to `rule_id + seed + stage_hash` |
| SDG6 Privacy | SYN* tickers, no real client IDs; utility = workflow coverage |
| SDG7 Composition | Stage modules with unit tests |

### Provenance manifest (required fields)

- `generator_version`, `seed`, `cohort_id`, `axiom_set_hash`
- `stage_outputs[]`, `parent_scenario_id` (for extensions)
- `tension_tags[]`, `ips_scope`

---

## Cohort Profiles

Sample `wealth_source` first, then draw sleeve weights from profile-specific priors
(not a global Dirichlet).

### `general_hnw` ($5M–$15M investable)

| Sleeve | Weight range | Structure |
| --- | --- | --- |
| equity | 0.45–0.65 | 1–2 taxable + 1 IRA |
| fixed_income | 0.15–0.30 | |
| cash | 0.05–0.15 | |
| alternatives | 0.05–0.15 | |

- Single-name max: 0.12
- Liquidity tier-1+2 ≥ 0.75
- Primary residence **out of IPS**

### `uhnw_inherited` ($30M–$150M)

| Sleeve | Weight range | Structure |
| --- | --- | --- |
| equity | 0.35–0.50 | trust + taxable + IRA |
| alternatives | 0.20–0.35 | 2–4 PE funds with unfunded |
| fixed_income | 0.10–0.20 | |
| cash | 0.05–0.10 | |
| commodities | 0.02–0.08 | |

- Liquidity tier-1+2 ≥ 0.55
- Entity graph: irrevocable trust + GRAT stub

### `founder_executive` ($10M–$100M)

| Sleeve | Weight range | Structure |
| --- | --- | --- |
| equity | 0.50–0.80 | includes concentration |
| alternatives | 0.05–0.20 | |
| fixed_income | 0.05–0.15 | |
| cash | 0.05–0.15 | |

- Concentrated issuer: 0.15–0.45 of equity sleeve
- QSBS flag on largest lot: 30% probability
- Optional NQDC account

### `concentrated_stress` (SDG2 counterfactual)

- Equity 0.70–0.90; single-name 0.25–0.60
- Intentionally stresses IPS breach, TLH, weight-only risk failure

---

## Rung Ladder

Aligns with [risk_api_contract.md](../risk_api_contract.md) synthetic corpus;

| Rung | Shape | Exercises | v1 target |
| --- | --- | --- | --- |
| 0 | single equity (β=1) | Level 1 σ/VaR smoke | shipped |
| 1 | 60/40 equity + FI | duration bucket, 2×2 cov | shipped |
| 2 | + commodities + FX | multi-asset aggregation | shipped |
| 3 | HNW 5-sleeve + liquidity tiers | cohort profiles, IPS min/max | **v1** |
| 4 | concentrated + fermi alts + multi-account lots | TLH, optimizer, recon, call stress | v1.1 |

Regression surface: **matrix `rung × run_scenarios`** with pinned golden values.

---

## Output Shapes

| Shape | Consumer | Contents |
| --- | --- | --- |
| A | Risk API | `AssetPortfolio` JSON (`source: synthetic`, `complexity: rung`) |
| B | Optimizer / recon / backtest | Full household fixture (graph + lots + alts sub-ledger) |
| C | Scenario catalog | Scenario card (`scenario_id`, `cohort_id`, `seed`, `generator_version`) |

### Lot split heuristics (rung 4)

- Concentrated name: 3–8 lots (varying basis/dates)
- Index ETF: 1–2 lots
- Harvestable loss lot: 15% probability in taxable equity (TLH tests)

### Alt call schedule

- Poisson calls over 24 months
- Amount = `min(unfunded, 0.1 × committed)` per event
- Feeds liquidity ladder stress

---

## Base Rates

- An HNW portfolio is not a weight vector—it is a household-scoped property graph (entities, accounts, instruments, lots, contracts) with time-series marks, liquidity tiers, and IPS constraints; synthetic generators must emit graph-coherent instances or fail axiomatic fidelity (SDG1).
- Synthetic HNW portfolio generator should be compositional (SDG7): cohort profile → entity graph → account allocation → sleeve weights → lot split → alt sub-ledger → IPS validation → provenance manifest—each stage independently auditable and replaceable.
- Synthetic HNW portfolios fail downstream when generators optimize for marginal realism (weights) while violating structural axioms (lots, calls, entity ownership)—wealth platforms then ship optimizers that pass demo but fail pilot.
- US high-net-worth households ($3M–$30M investable) typically hold wealth across 12–18 distinct asset categories; ultra-high-net-worth ($30M+) add larger illiquid and operating-business sleeves—median dollar weight ordering differs materially by wealth source (founder vs inherited vs executive).
- Managing a family office portfolio decomposes into ten consideration clusters—(1) governance & IPS, (2) entity & household structure, (3) data & reconciliation, (4) strategic allocation & rebalancing, (5) after-tax optimization, (6) liquidity & cash flow, (7) alternatives & illiquids, (8) research & scenarios, (9) execution & operations, (10) reporting & audit—with failure concentrated in (3) and (6) not optimizer sophistication.
- Family office portfolios blend liquid public markets with illiquid alternatives (PE, VC, real estate, private credit)—management requires separate sub-ledger, manual marks, capital call/distribution calendar, and liquidity budgeting distinct from daily ETF rebalance.
- Family office portfolio management fails most often on data plane—not investment ideas—custodian ingest quality, symbology mapping, lot-level cost basis, and reconciliation breaks block every downstream workflow (IPS drift, TLH, reporting).
- Family office portfolio management requires digitized IPS as machine-readable constraints—min/max weights, concentration limits, liquidity floors, restricted lists, do-not-sell legacy lots, ESG exclusions—not prose PDFs alone.
- Family office research plane feeds decision plane with macro scenarios and after-tax backtests—not autonomous trading—walk-forward purge required; production client data isolated in research sandbox.
- A UHNW wealth platform's canonical data model is a property graph over entities and contracts with time-series holdings and event-sourced transactions—relational stores for ledger, graph or document for relationships, object store for documents, and columnar for analytics.
- InvestmentWarehouse is a tech-enabled multi-family office platform shell implementing Sharpe brief priorities—after-tax north star, five operational planes, six workflows—dashboard-first with `warehouse serve` as living status report.
- Historic synthetic backtests need the same catalog treatment as live runs: scenario cards, provenance manifests, query by repo/tag/generator, and extends edges when lengthening season count or adding regimes.

## Disconfirming Limits

- **Weight-only books** pass risk rungs 0–2 but fail lot-level TLH and wash-sale tests.
- **Independent sleeve draws** miss PE-call / equity-drawdown coupling (forced public liquidation).
- **Smooth alt marks** understate tail risk in liquidity crises.
- **Single-account synthetics** miss asset-location optima (IRA vs taxable).
- **Always-feasible IPS** produces sterile books — optimizer and drift monitor never bind.
- **Missing generator_version** in manifest hash causes silent regression.

## Uncertainty Drivers

- v1 generator may emit sleeve-level AssetPortfolio only (risk rungs) before full lot ledger—document rung explicitly (risk_api_contract rungs 0–2 vs 3–4).
- Whether v1 ships rung 3 only (sleeve + liquidity) before rung 4 (full lots)—phased delivery matches warehouse build order.
- How much concentration to inject without unrealistic every-book-is-FAANG—profile mixture handles tails.
- Build-vs-buy (native ledger vs Addepar/Orion) shifts which considerations are in-house vs vendor.
- Valuation methodology for alts (GP marks vs independent)—governance per family.

## Falsifiers

- Uniform Dirichlet on six sleeves passes IPS, TLH, and liquidity stress at same rate as cohort-conditioned generator.
- Synthetic HNW portfolio without lot granularity calibrates tax-aware optimizer equally to held-out real anonymized lots.
- Generator with SDG axioms disabled matches downstream task pass rate of full SDG generator.
- All four cohort profiles produce identical optimizer binding constraint sets.
- Tax-aware optimizer shows identical trade list diversity on 1000 synthetic households vs 100 real anonymized lots.

## Source Basis

- `hnw-portfolios-framework`
- `hnw-portfolios-generator-spec`
- `hnw-portfolios-cohort-profiles`
- `hnw-portfolios-sdg-heuristics`
- `hnw-portfolios-disconfirming`
- `hnw-asset-types-framework`
- `hnw-asset-types-value-ranking`
- `family-office-portfolio-framework`
- `family-office-alternatives-liquidity`
- `family-office-data-reconciliation`
- `family-office-ips-governance`
- `family-office-research-scenarios`
- `sharpe-infrastructure-data-models`
- `investmentwarehouse-platform-context`
- `synth-scenario-catalog`

## Next Questions

### Follow-Up — investigate next

1. What observable test, dataset, or experiment would most reduce the uncertainty that v1 generator may emit sleeve-level AssetPortfolio only (risk rungs) before full lot ledger—document rung explicitly (risk_api_contract rungs 0–2 vs 3–4), and how far would resolving it move the current credence of 0.89?
2. What concrete, pre-resolution indicator would let us monitor the falsifier 'Uniform Dirichlet on six sleeves passes IPS, TLH, and liquidity stress at same rate as cohort-conditioned generator' before 2026-06-26?
3. Does the reference class behind the graph axiom condition on the same regime and scope as the target, and does re-stratifying it shift the prior?

### Open Sub-Questions — from sources

- Minimum household graph depth for v1—single taxable account vs full trust stack?
- Host generator in Forecasting (`synthetic_financial.py` pattern) vs InvestmentWarehouse `warehouse/research/synthetic/`?
- Inject reconciliation breaks as SDG2 negation pack or separate fault-injection harness?
- Expose profile as `cohort_id` on AssetPortfolio provenance alongside `complexity` rung?
- Synthetic portfolio generator for stress testing illiquid + public combined books without client data?
- CLI triad scenario rebuild / validate / query alongside backtest catalog?
