# IPS

**An Investment Policy Statement (IPS)** is a formal, written document that outlines the investment objectives, guidelines, constraints, and governance framework for managing a portfolio, particularly for institutional investors, high-net-worth individuals, or family offices.

### Core Purpose
The IPS serves as the foundational governance document for investment decision-making. It translates the investor's (or family's) goals, risk tolerance, time horizon, and preferences into actionable rules that guide portfolio managers, advisors, and committees. It promotes discipline, consistency, and accountability, especially during market volatility.

### Key Components (Typical Structure)
A comprehensive IPS usually includes:
- **Objectives and Goals**: Return targets, income needs, growth requirements, and alignment with broader financial or philanthropic missions.
- **Risk Tolerance and Constraints**: Volatility limits, liquidity requirements, time horizons, and tax considerations.
- **Asset Allocation**: Strategic targets (e.g., equities, fixed income, alternatives), ranges, and rebalancing rules.
- **Investment Guidelines**: Permissible asset classes, prohibited investments, concentration limits, ESG or ethical exclusions, and manager selection criteria.
- **Roles and Responsibilities**: Duties of the investment committee, advisors, custodians, and oversight processes.
- **Performance Measurement and Monitoring**: Benchmarks, reporting frequency, and review procedures.

### Relevance to Family Office Portfolio Management
In the context you provided, the IPS is critical for **digitized, machine-readable implementation**. Traditional prose-based PDFs are insufficient for modern systems; instead, family offices increasingly require structured, enforceable constraints such as:
- Minimum/maximum weights for asset classes or securities.
- Concentration limits.
- Liquidity floors.
- Restricted lists or do-not-sell legacy holdings.
- ESG exclusions or other custom rules.

This enables automated compliance monitoring, portfolio optimization, risk systems, and algorithmic execution. A digitized IPS supports seamless integration with trading platforms, risk engines, and reporting tools, reducing manual errors and enhancing scalability for complex, multi-generational wealth.

If you are developing or refining a digitized IPS for family office use, it is advisable to structure it with both a human-readable narrative section and a companion machine-readable format (e.g., JSON, YAML, or database schema) to capture the constraints you mentioned. This aligns with best practices in professional wealth management.

---

## How IPS Governs Portfolio Optimization

*DHA research run `ips-portfolio-optimization-2026` · 2026-06-27 · credence 0.46 · [full terrain map](https://github.com/hcarstens/DHAResearchAgent/blob/main/runs/research/ips-portfolio-optimization-2026/20260627T120000Z0000/terrain_map.md)*

An IPS does not merely inform the optimizer—it **defines the feasible region, policy benchmark, and governance gates**. The optimizer maximizes **after-tax utility inside IPS bounds**, not unconstrained mean-variance.

### Governance pipeline

```text
Household tax state + lot ledger + digitized IPS
        ↓
IPS drift monitor (upstream trigger)
        ↓
Asset location layer
        ↓
Tax-aware rebalance / TLH optimizer
        ↓
Explainable trade list → advisor approval → staged execution
```

### Hard constraints (feasible region)

Must bind before tax overlays or factor optimization:

| IPS section | Optimizer mapping |
| --- | --- |
| Asset allocation targets | Min/max sleeve weight inequalities |
| Rebalancing rules | Turnover budget, minimum trade size |
| Concentration limits | Single-name and sector caps |
| Liquidity requirements | Liquidity gate constraints |
| Investment guidelines / prohibitions | Zero-weight or ban on security sets |
| Restricted lists / do-not-sell lots | Binary lot-level constraints |
| Wash-sale rules | 30-day cross-account graph constraints |

### Soft constraints (preference ordering)

Penalty terms or lexicographic priority—not hard infeasibility:

- Prefer long-term over short-term gains
- Defer low-basis sales; harvest high-basis losses
- Asset-locate bonds/REITs in tax-deferred accounts

### Objective encoding (not just bounds)

- **Policy benchmark** — tracking error vs strategic allocation
- **Cash-flow obligations** — recurring distributions via yield/dividends vs lot sales
- **After-tax utility** — net of short-term vs long-term capital gains rates

### Drift monitor → optimizer

Threshold bands (5/10/25% typical) trigger rebalance proposals. The optimizer receives the current drift vector and target weights from the **IPS version effective at run time**. Tax-aware optimization runs after IPS feasibility is confirmed.

### InvestmentWarehouse mapping (Phase 3)

1. **Tier 1 (prerequisite):** lot ledger, reconciliation, entity graph
2. **Tier 2 (IPS + optimizer):** digitized IPS, drift monitor, tax-aware optimizer v0, explainable trade lists, approval workflow
3. **Constraint library:** IPS min/max, wash-sale across household, restricted lists, do-not-sell lots, turnover budget, minimum cash

### Failure modes

- **Prose-only IPS** — cannot enforce concentration or do-not-sell at lot level
- **Weight-only data (no lots)** — infeasible or non-compliant trade lists
- **Always-feasible IPS** — binding constraints never exercised in testing
- **Naive rebalance into structural drawdown** — hard stops must override underweight-buy rules
- **Optimizer before reconciliation** — IPS constraints applied to wrong positions
- **Pre-tax optimization** — violates IPS spirit when after-tax outcomes are mandated
- **Estate vs IPS conflict** — step-up at death may conflict with weight targets for elderly HNW

---

## DHA Domain Writer Summary

<!-- source: DHAResearchAgent/runs/research/ips-portfolio-optimization-2026/20260627T120000Z0000/domain_writer/summary.md -->

# How does an IPS document govern portfolio optimization?

Run status: `complete`

Research quality score: `10/10`

## Bottom Line

Synthesis for 'How does an IPS document govern portfolio optimization?': 83 supporting claim(s), 29 disconfirming claim(s); deterministic credence 0.456. 14 open sub-question(s) recorded.

## Base Rates

- An Investment Policy Statement (IPS) is a formal, written document outlining investment objectives, guidelines, constraints, and governance for managing a portfolio—particularly for institutional investors, high-net-worth individuals, and family offices.
- IPS governs portfolio optimization by defining the feasible region (hard constraints), policy benchmark (tracking target), and governance gates (approval workflow)—the optimizer maximizes after-tax utility inside IPS bounds, not unconstrained mean-variance.
- IPS-to-optimizer pipelines fail most often when IPS is prose-only, weight-only (no lots), or always-feasible—optimizer passes demo but breaches mandate in pilot or stress.
- Family office portfolio management requires digitized IPS as machine-readable constraints—min/max weights, concentration limits, liquidity floors, restricted lists, do-not-sell legacy lots, ESG exclusions—not prose PDFs alone.
- Tax-aware investment optimization at family offices combines (1) after-tax return expectations, (2) lot-level trade constraints, (3) multi-account asset location, and (4) household-level tax bracket dynamics—typically solved as constrained optimization or heuristic trade-priority rules when full MIP is too slow.
- Investment-level tax arbitrage (no residency change) is the most scalable HNW vector—tax-loss harvesting, asset location, lot-level gain deferral, QSBS exclusion, muni vs taxable, Roth conversion timing—typically 0.3–2.0% annual after-tax uplift on $5M+ taxable wealth with concentrated equity, implementable via direct indexing and household-aware optimizers.
- Family office rebalance is paired trim-overweight / fund-underweight on IPS drift—drawdown assets often bought, run-up assets trimmed—with tax asymmetry: harvest drawdown substitutes first, defer trimming run-up winners in taxable accounts until drift forces.
- Equity sleeve risk stacks market beta, sector/factor tilts (value, momentum, quality), concentration (single name, sector), and tail (gap, long-range regime days)—multi-asset portfolio equity risk is conditional on correlation to rates, FX, and commodities in stress.
- Simple risk models for family office platforms cover (1) linear exposures—beta, duration, weight concentration, (2) trailing or EWMA volatility, (3) parametric or historical VaR on liquid sleeves, (4) named historical stress replay—sufficient for IPS drift and advisor review before GARCH, copulas, or full greek engines.
- Synthetic HNW portfolios fail downstream when generators optimize for marginal realism (weights) while violating structural axioms (lots, calls, entity ownership)—wealth platforms then ship optimizers that pass demo but fail pilot.
- Buying the drawdown via rebalance underperforms when the drawdown asset is in structural decline, momentum regime persists, or correlations go to one in crisis—significant fraction of decade-long windows for single-asset sleeves.
- Investment workflows at tech-enabled family offices decompose into data plane (ingest, master data, ledger), research plane (signals, scenarios, backtests), decision plane (IPS, optimization, approvals), execution plane (OMS, routing, settlement), and reporting plane (performance, risk, tax)—each with distinct SLAs and failure modes.
- InvestmentWarehouse is a tech-enabled multi-family office platform shell implementing Sharpe brief priorities—after-tax north star, five operational planes, six workflows—dashboard-first with `warehouse serve` as living status report.

## Uncertainty Drivers

- How ESG and ethical exclusions map to hard vs soft optimizer constraints varies by client mandate.
- ESG exclusions as hard ban vs soft penalty in optimizer—client-specific IPS interpretation.
- Asymmetric drift bands (wider for tax-deferred, tighter for taxable) rarely implemented but materially affect optimizer trigger frequency.
- Step-up in basis at death makes never-trim run-up rational for elderly HNW—IPS weight targets conflict with estate-optimal path.
- ESG and exclusion lists as hard vs soft constraints in optimizer—client-specific.
- Sharpe may target planning/simulation ("what if we move to TX and harvest $2M losses") more than daily auto-TLH like robo-advisors.
- LTCG rate increases would raise value of deferral and location but reduce muni relative appeal—scenario-dependent.
- TCJA sunset re-sorts deferral vs harvest priority 2028+.
- Mega-cap concentration in cap-weight indices concentrates portfolio equity risk in few names 2026+.
- Whether EWMA λ=0.94 alone is enough dynamic vol for $50M–$200M liquid US family book post-2022.
- How much concentration to inject without unrealistic every-book-is-FAANG—profile mixture handles tails.
- How to detect structural vs cyclical drawdown before rebalance—no consensus indicator.
- Sharpe may prioritize simulation and planning over live trading in first six months given "optimization" and "wealth data model" emphasis in company overview.
- Heuristic agents and report writer integration with dashboard and approval gates—in TODO open questions.

## Falsifiers

- Prose-only IPS achieves same optimizer compliance rate as digitized IPS on concentrated UHNW books.
- Tax-agnostic rebalance to IPS targets beats tax-aware optimizer constrained by same IPS on after-tax wealth over 10y concentrated US equity family book.
- Optimizer with IPS hard constraints shows identical trade list diversity on weight-only vs lot-level books.
- Household with digitized IPS shows no reduction in ad-hoc discretionary trades vs prose IPS.
- Over-tight IPS (always feasible) produces same downstream optimizer stress coverage as realistically binding IPS in synthetic test harness.
- Prose-only IPS with no machine-readable companion achieves same optimizer compliance rate as digitized IPS on concentrated UHNW books.
- Tax-agnostic rebalance to IPS targets beats tax-aware optimizer constrained by same IPS on after-tax wealth over 10y concentrated US equity family book.
- Optimizer with IPS hard constraints shows identical trade list diversity on weight-only vs lot-level books—lot granularity adds no compliance value.
- Household with digitized IPS shows no reduction in ad-hoc discretionary trades vs prose IPS.
- Optimization framework that optimizes pre-tax Sharpe only while marketing tax-aware outcomes.
- Walk-forward after-tax backtest of household optimizer fails to beat static asset-location policy by >25bps annual on 2015–2025 US data.
- Tax-agnostic rebalance beats tax-aware overlay on after-tax wealth 10y concentrated US equity family book.
- Single-name cap enforcement fails to reduce max drawdown vs unconstrained book in 2008-style credit-equity crash.
- Simple beta+duration+concentration dashboard predicts IPS binding violations as well as full factor model on concentrated 20-name equity book 2020–2025.
- Tax-aware optimizer shows identical trade list diversity on 1000 synthetic households vs 100 real anonymized lots—synthetic adds no test coverage (SDG3 retire).
- Contrarian rebalance into worst-performing asset class each year beats equal-weight 1990–2025 G7 markets.
- Investment workflows that skip reconciliation and operate on custodian API snapshots without lot ledger support tax-aware recommendations at scale.
- Dashboard panels show stub data while backend claims live reconciliation—violates dashboard-first rule.

## Source Basis

- `investmentwarehouse-ips-context`
- `ips-portfolio-optimization-framework`
- `ips-portfolio-optimization-disconfirming`
- `family-office-ips-governance`
- `sharpe-tax-optimization-framework`
- `investment-level-tax-overlay`
- `family-office-tax-rebalance`
- `equity-portfolio-risk`
- `simple-risk-models-framework`
- `hnw-portfolios-disconfirming`
- `rebalance-disconfirming-momentum-wins`
- `sharpe-investment-workflows-systems`
- `investmentwarehouse-platform-context`

## Next Questions

### Follow-Up — investigate next

1. What observable test, dataset, or experiment would most reduce the uncertainty that how ESG and ethical exclusions map to hard vs soft optimizer constraints varies by client mandate, and how far would resolving it move the current credence of 0.46? — This is the run's leading uncertainty driver, so settling it has the highest expected information value.
2. What concrete, pre-resolution indicator would let us monitor the falsifier 'Prose-only IPS achieves same optimizer compliance rate as digitized IPS on concentrated UHNW books' before 2026-06-27, rather than only learning the answer at resolution? — A falsifier you cannot observe in advance cannot guide updating, so operationalizing it turns the caveat into an actionable check.
3. Does the reference class behind 'An Investment Policy Statement (IPS) is a formal, written document outlining investment objectives, guidelines, constraints, and governance for managing a portfolio—particularly for institutional investors, high-net-worth individuals, and family offices' condition on the same regime and scope as the target, and does re-stratifying it shift the prior? — A mis-specified reference class is a common source of miscalibrated base rates.

### What-If — negation probes

1. What if the disconfirming evidence is wrong and 'IPS-to-optimizer governance chain: digitized policy objects, hard vs soft constraints, objective encoding (after-tax utility, cash-flow obligations), drift monitor triggers, constraint hierarchy (weights, concentration, liquidity, exclusions, do-not-sell lots), explainability and advisor approval gates, failure modes when IPS is prose-only or always-feasible; mapping to InvestmentWarehouse tax-aware optimizer and five-plane workflow' holds before 2026-06-27? — Negating the prevailing lean (credence 0.46); taking the rejected outcome seriously can reveal an under-priced opportunity.
2. What if we treated the routing guardrail — '¬M1 — What if the system is irreducible? (Emergent properties, complexity)' — as the opportunity rather than the thing to avoid? — Heuristic Algebra negation of the active heuristic surfaces paths the default routing suppresses by design.

### Open Sub-Questions — from sources

- Standard schema for IPS constraint objects (weights, concentration, liquidity, exclusions) across custodians and optimizers?
- IPS version effective-dating and replay when tax law or mandate changes mid-year—how does optimizer select constraint set?
- Minimum IPS drift threshold to justify realizing gains on run-up sleeve—optimizer vs drift monitor coordination?
- IPS hard stop—never rebalance into single-name drawdown below X% of portfolio—as override rule in optimizer constraint library?
- IPS version effective-dating and replay when tax law changes mid-year?
- Does Sharpe model AMT, NIIT, QSBS, and trust distributable net income in v0 or defer to external tax engine?
- Integrate redomiciling scenario (state residency change) as optimizer input alongside lot ledger—tax rate vector per simulation job?
- Minimum IPS drift to justify realizing gains on run-up sleeve?
- Regime-conditioned equity beta to rates for hedge ratio scheduling?
- Ship simple risk manifest JSON alongside IPS drift panel at warehouse serve?
- Inject reconciliation breaks as SDG2 negation pack or separate fault-injection harness?
- IPS hard stop: never rebalance into single-name drawdown below X% of portfolio?
- Which workflows are in-scope for v1 pilot—full rebalance or tax-loss harvest opportunistic only?
- Sync family-office consideration manifest to InvestmentWarehouse docs/research/ after each DHA run?
