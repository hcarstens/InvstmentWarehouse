# What simple risk models should a family office platform implement first?

Run status: `complete`

Research quality score: `10/10`

## Bottom Line

Synthesis for 'What simple risk models should a family office platform implement first?': 50 supporting claim(s), 20 disconfirming claim(s); deterministic credence 0.892. 10 open sub-question(s) recorded.

## Base Rates

- Simple risk models for family office platforms cover (1) linear exposures—beta, duration, weight concentration, (2) trailing or EWMA volatility, (3) parametric or historical VaR on liquid sleeves, (4) named historical stress replay—sufficient for IPS drift and advisor review before GARCH, copulas, or full greek engines.
- Linear exposure models aggregate position-level sensitivities—equity beta to benchmark, fixed-income modified duration, sector and single-name weight concentration—portfolio exposure is sum of position × sensitivity × notional; no covariance required for exposure limits.
- EWMA (λ=0.94 daily) updates variance σ²_t = λσ²_{t-1} + (1-λ)r²_{t-1}—industry default for simple dynamic vol—feeds parametric VaR: VaR_α = -μ + z_α σ √(h) for horizon h days on elliptical return assumption.
- Historical simulation VaR takes empirical quantile of past portfolio returns (or factor-scaled position returns) over rolling window—no Gaussian assumption—named stress replay applies fixed historical factor shocks (2008, 2020, 2022) to current positions for advisor-readable P&L impact.
- Simple risk models fail when (1) book contains material non-linear exposure (options, structured notes), (2) illiquid alts marked monthly, (3) correlations regime-shift, (4) exposure definition wrong (swaps, leverage)—escalate to greeks, haircut factors, or stress grid rather than trust EWMA VaR.
- Simple risk model build order for InvestmentWarehouse: (1) lot-accurate positions, (2) exposure panel—beta, duration, concentration, liquidity tier, (3) EWMA vol per sleeve, (4) parametric + historical 1-day VaR/ES, (5) named stress replay, (6) breach/backtest flags on dashboard—defer GARCH, Monte Carlo, greek engine to Phase 4+ unless escalation triggers fire.
- Multi-asset portfolio risk management decomposes into (1) risk measurement, (2) risk budgeting/allocation, (3) tail and liquidity risk, (4) instrument-specific factor exposures, (5) hedging and overlays, (6) governance and limits—with failure most often from stale correlations, illiquid marks, and options gamma ignored until expiry week.
- Portfolio risk management fails when models use stale correlations, ignore liquidity, treat options as linear, mark alts smoothly, or hedge with wrong instrument—risk committees approve limits that breach in first systemic event.
- InvestmentWarehouse is a tech-enabled multi-family office platform shell implementing Sharpe brief priorities—after-tax north star, five operational planes, six workflows—dashboard-first with `warehouse serve` as living status report.
- Managing a family office portfolio decomposes into ten consideration clusters—(1) governance & IPS, (2) entity & household structure, (3) data & reconciliation, (4) strategic allocation & rebalancing, (5) after-tax optimization, (6) liquidity & cash flow, (7) alternatives & illiquids, (8) research & scenarios, (9) execution & operations, (10) reporting & audit—with failure concentrated in (3) and (6) not optimizer sophistication.

## Uncertainty Drivers

- Whether EWMA λ=0.94 alone is enough dynamic vol for $50M–$200M liquid US family book post-2022.
- Mega-cap index concentration makes benchmark beta understate single-name risk for cap-weighted passive sleeves.
- Daily-close VaR misses intraday gap risk on concentrated single-stock books.
- Optimal rolling window length (126 vs 252 vs 504 days) for family office with quarterly rebalance.
- Threshold percentages for escalation triggers vary by IPS liquidity and advisor risk appetite.
- In-process SQLite sufficient for nightly EWMA refresh vs need Phase 5 job queue for multi-household pilot.
- LLM-accelerated factor crowding compresses hedge effectiveness on published risk premia sleeves.
- Cost of always-on tail hedging vs episodic crisis—budget constraint for family offices.
- Heuristic agents and report writer integration with dashboard and approval gates—in TODO open questions.
- Build-vs-buy (native ledger vs Addepar/Orion) shifts which considerations are in-house vs vendor.

## Falsifiers

- Simple beta+duration+concentration dashboard predicts IPS binding violations as well as full factor model on concentrated 20-name equity book 2020–2025.
- EWMA parametric 1-day 95% VaR breaches on fewer than 8% of days for SPY-only book walk-forward 2010–2025.
- Family office with simple-only stack reports fewer surprise drawdowns than peer with vendor GARCH stack 2018–2025.
- 252-day historical 95% VaR breaches more than 8% of days on 60/40 portfolio 2010–2025 walk-forward.
- Simple risk panel live without new reconciliation breaks in 90-day pilot.
- Simple beta+duration+concentration dashboard predicts IPS binding violations as well as full factor model on concentrated 20-name equity book 2020–2025.
- Portfolio beta alone forecasts 1-month drawdown magnitude within 20% RMSE for diversified 30-stock US book 2015–2025.
- EWMA parametric 1-day 95% VaR breaches on fewer than 8% of days for SPY-only book walk-forward 2010–2025.
- 252-day historical 95% VaR breaches more than 8% of days on 60/40 portfolio 2010–2025 walk-forward.
- Family office with simple-only stack (no escalation) reports fewer surprise drawdowns than peer with vendor GARCH stack 2018–2025.
- Simple risk panel live without new reconciliation breaks in 90-day pilot.
- Static 60/40 correlation matrix risk model predicts 2022 bond-equity joint drawdown within 1σ band.
- Median institutional multi-asset fund with formal risk system beats passive 60/40 on max drawdown 2000–2025 net of hedge cost.
- Dashboard panels show stub data while backend claims live reconciliation—violates dashboard-first rule.
- Median greenfield family office platform reaches advisor trust without lot-level reconciliation in first 12 months.

## Source Basis

- `simple-risk-models-framework`
- `simple-risk-models-exposures`
- `simple-risk-models-ewma-var`
- `simple-risk-models-historical-stress`
- `simple-risk-models-disconfirming`
- `simple-risk-models-checklist`
- `portfolio-risk-management-framework`
- `portfolio-risk-disconfirming`
- `investmentwarehouse-platform-context`
- `family-office-portfolio-framework`

## Next Questions

### Follow-Up — investigate next

1. What observable test, dataset, or experiment would most reduce the uncertainty that whether EWMA λ=0.94 alone is enough dynamic vol for $50M–$200M liquid US family book post-2022, and how far would resolving it move the current credence of 0.89? — This is the run's leading uncertainty driver, so settling it has the highest expected information value.
2. What concrete, pre-resolution indicator would let us monitor the falsifier 'Simple beta+duration+concentration dashboard predicts IPS binding violations as well as full factor model on concentrated 20-name equity book 2020–2025' before 2026-06-24, rather than only learning the answer at resolution? — A falsifier you cannot observe in advance cannot guide updating, so operationalizing it turns the caveat into an actionable check.
3. Does the reference class behind 'Simple risk models for family office platforms cover (1) linear exposures—beta, duration, weight concentration, (2) trailing or EWMA volatility, (3) parametric or historical VaR on liquid sleeves, (4) named historical stress replay—sufficient for IPS drift and advisor review before GARCH, copulas, or full greek engines' condition on the same regime and scope as the target, and does re-stratifying it shift the prior? — A mis-specified reference class is a common source of miscalibrated base rates.

### What-If — negation probes

1. What if the supporting evidence reverses and 'Minimum viable risk stack: linear exposures (beta, duration, concentration), EWMA vol, parametric and historical VaR/ES, named stress replay; disconfirming limits and escalation triggers; InvestmentWarehouse Phase 3 dashboard mapping; defer GARCH/copulas/Monte Carlo until simple stack trusted' instead fails before 2026-06-24? — Negating the prevailing lean (credence 0.89); pricing the disconfirming regime as the base case can reveal a hedge or contrarian edge the current view suppresses.
2. What if we treated the routing guardrail — '¬M1 — What if the system is irreducible? (Emergent properties, complexity)' — as the opportunity rather than the thing to avoid? — Heuristic Algebra negation of the active heuristic surfaces paths the default routing suppresses by design.

### Open Sub-Questions — from sources

- Ship simple risk manifest JSON alongside IPS drift panel at warehouse serve?
- Expose beta, duration, concentration in constraint binding report per household?
- Dashboard panel: VaR, ES, breach count, last 20-day EWMA vol per household?
- Pre-register simple stress pack (2008/2020/2022) in research sandbox config hash?
- Document escalation triggers in machine-readable IPS companion schema?
- Add simple risk panel to warehouse.dashboard.phases as Phase 3 upgrade or Phase 4 stub?
- Unified risk manifest per household: factor exposures × liquidity tier × mark cadence?
- Minimum viable risk stack for $50M family office without full risk vendor?
- Sync family-office consideration manifest to InvestmentWarehouse docs/research/ after each DHA run?
- Unified consideration scorecard per household with friction-weighted priority queue?
