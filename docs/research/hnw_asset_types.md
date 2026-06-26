# What types of assets does a high-net-worth individual typically hold—and how are they ordered by likely relative dollar value?

US-centric HNW/UHNW asset taxonomy for wealth management: enumerate types, rank by
typical aggregate dollar weight (not return), and map to InvestmentWarehouse data
model and IPS sleeves.

**Research run:** `runs/research/hnw-asset-types-2026/20260626T120000Z0000/`
(quality score 10/10, credence 0.89)

**Config:** `configs/research_agents/hnw_asset_types_20260626.json`

Run status: `complete`

Research quality score: `10/10`

## Bottom Line

Synthesis for 'What types of assets does a high-net-worth individual typically hold—and how are they ordered by likely relative dollar value?': 70 supporting claim(s), 18 disconfirming claim(s); deterministic credence 0.892. 8 open sub-question(s) recorded.

Rankings are by typical **aggregate dollar weight**, not expected return. A single
global order does not fit all households — cohort matters (founder vs inherited vs
executive vs general HNW).

## Asset Type Taxonomy

| Cat | Asset type | Examples | Platform notes |
| --- | --- | --- | --- |
| A | Operating business / private company equity | Closely held C-corp, S-corp, LLC, pre-IPO | Manual marks; entity-graph ownership |
| B | Public market equities | Stocks, ETFs, mutual funds, SMAs, direct indexing | Custodian-fed; lot-level TLH |
| C | Real estate | Primary home, rentals, REITs, private RE funds, land | Property-level debt on entity graph |
| D | Private equity & venture capital | Buyout, growth, VC LPs, co-invests | Capital-call calendar required |
| E | Fixed income & cash | Treasuries, munis, CDs, MMFs, short bond funds | Liquidity sleeve; muni TEY overlay |
| F | Retirement & tax-advantaged | 401(k), IRA, Roth, HSA, NQDC | Asset-location pairing with taxable book |
| G | Concentrated employer / founder stock | RSUs, options, legacy single-name, pre-IPO employer equity | QSBS + IPS concentration caps |
| H | Private credit & direct lending | Private debt funds, direct loans, BDCs | Liquidity tier 2–3 |
| I | Hedge funds & liquid alts | L/S equity, macro, multi-strat | More common at UHNW; gating risk |
| J | Real assets & commodities | Farmland, timber, O&G, gold, commodity ETFs | Fermi marks common |
| K | Art, collectibles, passion assets | Art, wine, cars, jewelry | Low liquidity; often under-reported |
| L | Cryptocurrency & digital assets | BTC, ETH, stablecoins, tokenized RWAs | Tax character (988); custody matters |
| M | Cash-value insurance & annuities | Whole life, IUL, SPIAs, PPLI | Estate-liquidity wrapper |
| N | Philanthropic capital | DAF, private foundation, CRT interests | Outside spendable IPS numerator |
| O | Personal-use tangible assets | Aircraft, yachts, vehicles | Balance sheet only; excluded from IPS |

**InvestmentWarehouse sleeve rollup** (`AssetClass` enum): B/G → `equity`; E →
`fixed_income` / `cash`; D/H/I + direct RE → `alternatives`; J → `commodities`;
FX hedges → `fx`.

## Ranked by Likely Relative Value

### Cohort 1 — Median HNW ($5M–$15M, general)

1. Public market equities & funds
2. Primary residence (real estate)
3. Fixed income & cash
4. Retirement accounts
5. Other real estate
6. Private investments / alts
7. Business interests
8. Insurance / annuities
9. Art / collectibles
10. Crypto
11. Personal-use assets
12. Philanthropic vehicles

### Cohort 2 — UHNW ($30M+, diversified / inherited)

1. Public market equities
2. Private equity / VC
3. Real estate (all)
4. Fixed income & cash
5. Hedge funds / liquid alts
6. Private credit
7. Business interests
8. Retirement accounts
9. Real assets
10. Insurance structures
11. Art / collectibles
12. Crypto
13. Philanthropic
14. Personal-use

### Cohort 3 — UHNW founder / executive

1. Business equity **or** concentrated employer stock
2. Public market equities (diversified sleeve)
3. Real estate
4. Private equity / VC (personal LP)
5. Cash / fixed income
6. Retirement / NQDC
7. Crypto (optional)
8. Insurance / estate structures
9. Art / collectibles
10. Philanthropic
11. Personal-use

### InvestmentWarehouse v1 default (blended US taxable household)

Ingest and modeling priority:

1. Public equities
2. Fixed income / cash
3. Retirement accounts
4. Real estate
5. PE / VC
6. Concentrated single-name
7. Private credit
8. Hedge funds
9. Real assets
10. Insurance wrappers
11. Art / collectibles
12. Crypto
13. Business interests (manual)
14. Philanthropic (manual)
15. Personal-use (out of IPS)

## Base Rates

- US high-net-worth households ($3M–$30M investable) typically hold wealth across 12–18 distinct asset categories; ultra-high-net-worth ($30M+) add larger illiquid and operating-business sleeves—median dollar weight ordering differs materially by wealth source (founder vs inherited vs executive).
- For US HNW wealth management, order asset types by typical aggregate dollar weight (not return) using three reference cohorts—(1) median HNW $5M–$15M general, (2) UHNW $30M+ diversified, (3) UHNW founder/executive—with ranks 1 = largest typical share.
- InvestmentWarehouse implements a phased asset-type coverage model—custodian-fed liquid securities first, manual private/alt sub-ledger second, entity-graph real estate and business interests third—with IPS constraints expressed on rolled-up sleeves (equity, fixed_income, commodities, fx, alternatives, cash) plus concentration overlays.
- Family office portfolios blend liquid public markets with illiquid alternatives (PE, VC, real estate, private credit)—management requires separate sub-ledger, manual marks, capital call/distribution calendar, and liquidity budgeting distinct from daily ETF rebalance.
- A UHNW wealth platform's canonical data model is a property graph over entities and contracts with time-series holdings and event-sourced transactions—relational stores for ledger, graph or document for relationships, object store for documents, and columnar for analytics.
- Investment workflows at tech-enabled family offices decompose into data plane (ingest, master data, ledger), research plane (signals, scenarios, backtests), decision plane (IPS, optimization, approvals), execution plane (OMS, routing, settlement), and reporting plane (performance, risk, tax)—each with distinct SLAs and failure modes.
- InvestmentWarehouse is a tech-enabled multi-family office platform shell implementing Sharpe brief priorities—after-tax north star, five operational planes, six workflows—dashboard-first with `warehouse serve` as living status report.
- Ranking tax arbitrage vectors for US HNW by expected net after-tax benefit minus friction (compliance, legal, family, reputational) over 5y horizon yields: Tier 1 investment overlay, Tier 2 US state residency, Tier 3 entity/domestic trust, Tier 4 foreign residency (non-citizen or expatriation path), Tier 5 aggressive offshore stacking (generally disfavored for US persons).

## Platform Mapping

- **Phase 2 ingest (automated):** public equities, ETFs, mutual funds, listed bonds, munis, CDs, MMFs, listed REITs, listed BDCs, options on listed underlyings.
- **Phase 2 ingest (semi-automated):** retirement accounts at major custodians with account-type tax wrapper flag.
- **Phase 4 manual sub-ledger:** PE, VC, private credit, hedge funds, direct real estate, farmland — vintage, unfunded commitment, last mark, next call date, liquidity tier 3.
- **Entity graph:** primary residence and investment property as Property nodes; operating business as BusinessInterest; philanthropic as DAF/Foundation — holistic balance sheet, not all in optimizer v0.
- **Liquidity tiers:** Tier 1 (T+1 public) → Tier 2 (interval/gated) → Tier 3 (PE calls, direct RE).

## Uncertainty Drivers

- 2026–2030 rate path shifts fixed-income vs equity relative value at margin—not category presence.
- 2026 estate exemption sunset may elevate insurance (rank ~8–10) and philanthropic (rank ~12–14) planning flows without changing long-run median weights.
- Build-vs-buy for alt admin (iCapital, CAIS, Canoe) vs native sub-ledger changes ingest depth for ranks 5–8 asset types.
- Valuation methodology for alts (GP marks vs independent)—governance per family.
- Sharpe stack choice (Python quant + TypeScript product vs all-Python vs .NET custodian integrations) not stated in PDF.
- Sharpe may prioritize simulation and planning over live trading in first six months given "optimization" and "wealth data model" emphasis in company overview.
- Heuristic agents and report writer integration with dashboard and approval gates—in TODO open questions.
- TCJA sunset and state millionaire taxes re-sort Tier 2 vs Tier 1 deferral value by 2028.

## Falsifiers

- Fed SCF or Capgemini median UHNW mix shows public equities below 5% aggregate weight 2020–2025.
- Survey median for $10M US HNW shows alternatives aggregate weight exceeds public equities 2018–2025.
- Longitudinal panel shows fewer than 20% of US HNW households change top-3 asset-category ranks over any 5y window.
- IPS drift monitor accurate when PE/VC unfunded commitments excluded from liquidity stress.
- Single global asset-type ranking fits founder, inherited, and retiree cohorts without re-stratification.
- Fed SCF or Capgemini median UHNW asset mix shows public equities below 5% aggregate weight 2020–2025—contradicts liquid-sleeve dominance for non-founder cohort.
- Survey median for $10M US HNW shows alternatives (PE+HF) aggregate weight exceeds public equities 2018–2025—contradicts Cohort 1 ordering.
- IPS drift monitor accurate when PE/VC unfunded commitments excluded from liquidity stress—cash shortfall on capital calls.
- Family office with >40% alts and no call calendar experiences zero forced liquidations of public sleeve over 10y.
- Data model that stores only account-level weights without lot granularity while claiming tax optimization support.
- Investment workflows that skip reconciliation and operate on custodian API snapshots without lot ledger support tax-aware recommendations at scale.
- Dashboard panels show stub data while backend claims live reconciliation—violates dashboard-first rule.
- Empirical panel shows Tier 4 median NPV beats Tier 1 for $10M–$50M cohort 2026–2031—contradicts friction-adjusted ranking.

## Disconfirming Limits

- **Primary residence** is often the largest single asset at $3M–$8M but is usually excluded from investable IPS.
- **Post-IPO founders** can be 70–90% single stock temporarily — ranks invert until diversification.
- **Multi-gen UHNW** may hold 30–50% in private markets — public equity is not always #1.
- **Gross vs net:** mortgages and SBLOCs change effective weights.
- **Survey bias:** self-report understates alts and insurance, overstates cash.

## Source Basis

- `hnw-asset-types-framework`
- `hnw-asset-types-value-ranking`
- `hnw-asset-types-platform-mapping`
- `family-office-alternatives-liquidity`
- `sharpe-infrastructure-data-models`
- `sharpe-investment-workflows-systems`
- `investmentwarehouse-platform-context`
- `hnw-tax-arbitrage-ranking`

## Next Questions

### Follow-Up — investigate next

1. What observable test, dataset, or experiment would most reduce the uncertainty that 2026–2030 rate path shifts fixed-income vs equity relative value at margin—not category presence, and how far would resolving it move the current credence of 0.89? — This is the run's leading uncertainty driver, so settling it has the highest expected information value.
2. What concrete, pre-resolution indicator would let us monitor the falsifier 'Fed SCF or Capgemini median UHNW mix shows public equities below 5% aggregate weight 2020–2025' before 2026-06-26, rather than only learning the answer at resolution? — A falsifier you cannot observe in advance cannot guide updating, so operationalizing it turns the caveat into an actionable check.
3. Does the reference class behind 'US high-net-worth households ($3M–$30M investable) typically hold wealth across 12–18 distinct asset categories; ultra-high-net-worth ($30M+) add larger illiquid and operating-business sleeves—median dollar weight ordering differs materially by wealth source (founder vs inherited vs executive)' condition on the same regime and scope as the target, and does re-stratifying it shift the prior? — A mis-specified reference class is a common source of miscalibrated base rates.

### What-If — negation probes

1. What if the supporting evidence reverses and 'Enumerate HNW/UHNW asset type taxonomy for US wealth management; rank by typical aggregate dollar weight (not return) across cohorts; map to InvestmentWarehouse security master, IPS sleeves, liquidity tiers, and five-plane workflows; disconfirming limits on ranking stability' instead fails before 2026-06-26? — Negating the prevailing lean (credence 0.89); pricing the disconfirming regime as the base case can reveal a hedge or contrarian edge the current view suppresses.
2. What if we treated the routing guardrail — '¬M1 — What if the system is irreducible? (Emergent properties, complexity)' — as the opportunity rather than the thing to avoid? — Heuristic Algebra negation of the active heuristic surfaces paths the default routing suppresses by design.

### Open Sub-Questions — from sources

- Should InvestmentWarehouse IPS default taxonomy use 6 sleeve AssetClass enum or expand to 15+ leaf types for optimizer constraints?
- Publish cohort selector in IPS JSON (`wealth_source: founder|inherited|executive|general`) to pick default asset-type prior for Fermi marks?
- Minimum leaf-type enum for security master v1—15 types vs 40+ FINRA/CUSIP asset categories?
- Synthetic portfolio generator for stress testing illiquid + public combined books without client data?
- Event sourcing for entire platform vs snapshot-plus-delta for simulations only?
- Which workflows are in-scope for v1 pilot—full rebalance or tax-loss harvest opportunistic only?
- Sync family-office consideration manifest to InvestmentWarehouse docs/research/ after each DHA run?
- Publish per-vector friction scores in next_questions.md for walk-forward validation against client outcomes?
