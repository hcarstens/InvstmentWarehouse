# Asset allocation rebalancing: should you rebalance an asset under drawdown or an asset under run-up?

Run status: `complete`

Research quality score: `10/10`

## Bottom Line

Synthesis for 'Asset allocation rebalancing: should you rebalance an asset under drawdown or an asset under run-up?': 59 supporting claim(s), 26 disconfirming claim(s); deterministic credence 0.696. 11 open sub-question(s) recorded.

## Base Rates

- Strategic asset allocation rebalancing restores policy weights—by construction it buys underweight assets (often recent drawdowns) and trims overweight assets (often recent run-ups); calendar (quarterly/annual) and threshold (5/10/25 band) rules dominate institutional implementation over discretionary timing.
- Buying assets under drawdown via rebalancing earns a "rebalancing premium" when asset returns are negatively correlated or volatility-dominated—selling the run-up asset funds purchases of the cheaper drawdown asset, improving buy-low-sell-high execution vs static weights.
- Trimming assets in run-up via rebalancing is selling relative strength—this conflicts with cross-asset momentum at 3–12 month horizons where winners continue to win; tactical allocators sometimes delay rebalance or rebalance into run-ups (momentum tilt) when trend regime detected.
- For taxable HNW portfolios, rebalance direction is tax-asymmetric—assets in drawdown are candidates for tax-loss harvest (sell loser, buy substitute); assets in run-up are costly to trim (realize gains)—optimal rebalance often harvests drawdowns first and defers trimming run-ups until risk drift forces it.
- Risk-budget rebalancing adjusts positions when risk contributions drift—not raw weights—after a run-up with rising vol, the asset may be trimmed even if return momentum positive; after drawdown with vol spike, trim may be larger (vol targeting) or smaller (if correlation drops)—direction differs from naive buy-drawdown/sell-runup.
- Buying the drawdown via rebalance underperforms when the drawdown asset is in structural decline, momentum regime persists, or correlations go to one in crisis—significant fraction of decade-long windows for single-asset sleeves.
- For strategic multi-asset allocation, default rebalance action is symmetric on policy drift: trim the run-up (overweight) asset and fund the drawdown (underweight) asset—because IPS targets weights not momentum; exceptions arise for tax, risk-budget, momentum regime, and structural drawdown.
- Tax-aware investment optimization at family offices combines (1) after-tax return expectations, (2) lot-level trade constraints, (3) multi-account asset location, and (4) household-level tax bracket dynamics—typically solved as constrained optimization or heuristic trade-priority rules when full MIP is too slow.
- Global capital allocation can be modeled as a flow network: nodes are asset classes, venues, and balance-sheet slots; lanes are reallocation paths (cash → equities → bonds → commodities → alternatives); inventory is risk capital and margin capacity held at nodes.
- Difficulty of beating B&H over 2026–2031 is regime-conditional—cap-weight equity B&H wins in steady mega-cap grind; active and alternatives win in rotation, bear markets with hedging, or when B&H asset (long bond, long BTC) enters drawdown if manager avoided or shorted.
- Much of what funds called "alpha" was always compensated risk premia (carry, value, momentum crash risk, term premium)—LLM arbitrage strips illusory alpha first, leaving honest premia collection and true forecast skill as separate P&L lines.

## Uncertainty Drivers

- Optimal band width varies by asset correlation regime—tighter bands in low-vol, wider in crisis.
- Rebalancing premium magnitude post-2008 QE—correlations unstable; premium may be risk premia not free lunch.
- Regime classifier (trend vs mean-revert) to switch rebalance direction—not robust OOS in published tactical AA papers.
- TCJA LTCG sunset changes calculus of deferring run-up trims 2028+.
- Short vol vs long vol regime changes risk-parity rebalance direction quarterly.
- How to detect structural vs cyclical drawdown before rebalance—no consensus indicator.
- Optimal band width differs for run-up trim vs drawdown buy—asymmetric bands rarely implemented.
- Sharpe may target planning/simulation ("what if we move to TX and harvest $2M losses") more than daily auto-TLH like robo-advisors.
- Granularity at which logistics OR models (min-cost flow) transfer to capital networks without equilibrium violations.
- AI capex cycle exhaustion—Scenario C trigger or continued A.
- Whether clients accept lower stated "alpha" target (2–4% IR) on scenario sleeve versus legacy 15% backtest fantasy.

## Falsifiers

- Never-rebalance drift beats threshold two-way rebalance on after-tax Sharpe 20y US 60/40 walk-forward.
- Contrarian rebalance into worst-performing asset class each year beats equal-weight 1990–2025 G7.
- Delayed rebalance (trim run-up only after 12m negative momentum) beats standard threshold rebalance Sharpe 1990–2025.
- Asymmetric rebalance (only buy drawdown, never trim run-up) matches full two-way rebalance on risk-adjusted return 20y.
- Tax-agnostic threshold rebalance beats tax-aware overlay on after-tax wealth 10y concentrated US equity.
- Never-rebalance buy-and-hold policy weights beat threshold-rebalance on after-tax Sharpe over 20y US 60/40 walk-forward.
- Out-of-sample rebalancing premium negative for 60/40 2010–2025 monthly rebalance vs drift.
- Delayed rebalance (only trim run-up after 12m negative momentum signal) beats standard threshold rebalance Sharpe 1990–2025 multi-asset.
- Tax-agnostic threshold rebalance beats tax-aware overlay on after-tax wealth 10y concentrated US equity portfolio.
- Risk-budget rebalance fails to reduce max drawdown vs weight rebalance on 60/40 2000–2025.
- Contrarian rebalance into worst-performing asset class each year beats equal-weight 1990–2025 G7 markets.
- Asymmetric rebalance (only buy drawdown, never trim run-up) matches full two-way rebalance on risk-adjusted return 20y.
- Optimization framework that optimizes pre-tax Sharpe only while marketing tax-aware outcomes.
- Min-cost flow optimization on quarterly Z.1 graphs predicts monthly sector rotation better than factor models with equal data vintage.
- Cap-weight SPY B&H underperforms median active fund 2026–2031 in realized data.
- Post-reclassification, no sleeve labeled premia earns positive net Sharpe 2026–2031—everything was mislabeled beta.

## Source Basis

- `rebalancing-strategic-framework`
- `rebalance-drawdown-mean-reversion`
- `rebalance-runup-momentum`
- `rebalance-tax-after-tax`
- `rebalance-risk-budgeting`
- `rebalance-disconfirming-momentum-wins`
- `rebalance-decision-framework`
- `sharpe-tax-optimization-framework`
- `capital-flows-network-analogy`
- `beat-bh-regime-5y-forward`
- `risk-premia-vs-alpha-reclassification`

## Next Questions

### Follow-Up — investigate next

1. What observable test, dataset, or experiment would most reduce the uncertainty that optimal band width varies by asset correlation regime—tighter bands in low-vol, wider in crisis, and how far would resolving it move the current credence of 0.70? — This is the run's leading uncertainty driver, so settling it has the highest expected information value.
2. What concrete, pre-resolution indicator would let us monitor the falsifier 'Never-rebalance drift beats threshold two-way rebalance on after-tax Sharpe 20y US 60/40 walk-forward' before 2026-06-30, rather than only learning the answer at resolution? — A falsifier you cannot observe in advance cannot guide updating, so operationalizing it turns the caveat into an actionable check.
3. Does the reference class behind 'Strategic asset allocation rebalancing restores policy weights—by construction it buys underweight assets (often recent drawdowns) and trims overweight assets (often recent run-ups); calendar (quarterly/annual) and threshold (5/10/25 band) rules dominate institutional implementation over discretionary timing' condition on the same regime and scope as the target, and does re-stratifying it shift the prior? — A mis-specified reference class is a common source of miscalibrated base rates.

### What-If — negation probes

1. What if the supporting evidence reverses and 'Strategic vs tactical rebalance; mean reversion and rebalancing premium; momentum and trend conflict; tax-aware asymmetry (harvest drawdown, defer trim run-up); risk-budget rebalancing; disconfirming structural drawdown cases; default paired trim/buy framework' instead fails before 2026-06-30? — Negating the prevailing lean (credence 0.70); pricing the disconfirming regime as the base case can reveal a hedge or contrarian edge the current view suppresses.
2. What if we treated the routing guardrail — '¬E1 — Rationality fails when: emotions carry information, stakes are existential, or time is zero' — as the opportunity rather than the thing to avoid? — Heuristic Algebra negation of the active heuristic surfaces paths the default routing suppresses by design.

### Open Sub-Questions — from sources

- Default rebalance trigger: absolute weight drift vs risk-contribution drift?
- Condition rebalance on drawdown depth (e.g. only buy if drawdown >15% AND valuation signal)?
- Hybrid rule: strategic rebalance bands widened during confirmed momentum regime?
- Minimum IPS drift that justifies realizing gains on run-up asset?
- Publish joint rule: weight band OR risk band breach triggers rebalance— which binds first?
- IPS hard stop: never rebalance into single-name drawdown below X% of portfolio?
- Pre-register rebalance rule variants for 2026–2031 walk-forward in Forecasting backtest harness?
- Does Sharpe model AMT, NIIT, QSBS, and trust distributable net income in v0 or defer to external tax engine?
- Unified node taxonomy: asset × venue × investor sector for spiderweb + flow-of-funds merge?
- Probability-weighted difficulty score across scenarios?
- Standard disclosure template for arb-pressure score per sleeve?
