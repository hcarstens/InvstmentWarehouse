# How is portfolio risk measured—and what is a unit of risk?

Run status: `complete`

Research quality score: `10/10`

## Bottom Line

Synthesis for 'How is portfolio risk measured—and what is a unit of risk?': 59 supporting claim(s), 22 disconfirming claim(s); deterministic credence 0.696. 11 open sub-question(s) recorded.

## Base Rates

- "Unit of risk" is not one number—it is a family of commensurate measures chosen for a decision: (A) volatility units (σ, annualized %), (B) dollar loss units (VaR, ES at horizon h), (C) sensitivity units per factor (β, DV01, Δ, Γ, vega), (D) risk contribution units (% of portfolio variance or ES), (E) liquidity-time units (days to liquidate at X% ADV)—multi-asset books require explicit mapping between units, never silent aggregation.
- The most portable unit of risk across comparable assets is return volatility (σ)—typically annualized standard deviation of log or simple returns—variance (σ²) additive under independence but portfolio variance requires correlations; vol is unitless % enabling cross-asset comparison before dollar scaling.
- Dollar-denominated tail units translate distribution to P&L: VaR_α,h = quantile of loss distribution at confidence α over horizon h; ES (CVaR) = expected loss given loss exceeds VaR—ES is coherent risk measure, VaR is not subadditive but widely reported.
- Each asset class has native sensitivity units measuring $ P&L per unit move in risk factor—equities: beta ($ per 1% index move); rates: DV01 ($ per 1bp parallel shift); options: delta ($ per $1 underlying), gamma ($ per $1²), vega ($ per 1 vol point); FX: delta per 1% spot; commodities: $ per $1 or per tick—portfolio risk measurement aggregates these to common dollar delta-equivalents only approximately.
- Risk budgeting uses unit of marginal contribution: each sleeve's % of total portfolio variance (or ES)—sums to 100%; equal risk contribution (ERC) targets equal % from each sleeve—unit is dimensionless share of total risk not dollar or σ alone.
- Multi-asset risk measurement fails when unlike units are summed without bridge—correct aggregation paths: (1) simulate joint scenarios → single $ P&L distribution; (2) covariance matrix on synchronized return series → portfolio σ and VaR; (3) report sleeve-native units side-by-side without false total—illiquids get liquidity-time unit not daily VaR.
- Risk units mislead when precision exceeds accuracy—four decimal VaR on stale marks, beta from 5y monthly data on weekly-traded book, or single σ on fat-tailed sleeve—false commensurability worse than no number.
- Recommended unit hierarchy for multi-asset family office: Level 0 policy ($ max drawdown, liquidity days); Level 1 portfolio tail ($ ES_97.5, 1m horizon); Level 2 sleeve contribution (% ES or % vol); Level 3 native sensitivity (β, DV01, Δ, vega); Level 4 scenario $ (named stress P&L); never collapse levels without documenting approximation.
- Historical simulation VaR takes empirical quantile of past portfolio returns (or factor-scaled position returns) over rolling window—no Gaussian assumption—named stress replay applies fixed historical factor shocks (2008, 2020, 2022) to current positions for advisor-readable P&L impact.
- Multi-asset portfolio risk is regime-conditional—correlations compress toward +1 in liquidity crises (2008, 2020, 2022)—risk management requires stress scenarios and correlation shocks, not one historical covariance matrix.
- In a capital-allocation logistics framing, friction is the generalized cost of moving risk capital along a lane—bid-ask spread, market impact, funding rate, margin haircut, settlement delay, regulatory capital charge, and tax friction compound like logistics handling + toll + dwell time.

## Uncertainty Drivers

- Regime-conditional unit conversion (β to $ loss) breaks in crisis—stress units more honest than covariance units.
- Intraday vol for 0DTE options books vs daily risk committee cadence—unit mismatch.
- Which α family offices use vs banks (95% vs 99.5%)—unit not comparable across shops without metadata.
- Private equity reported beta to public markets is unstable—sensitivity unit noisy.
- After-tax risk contribution (harvesting changes weights) rarely computed—pre-tax unit only in practice.
- AI intraday structure may require hourly risk unit for options books vs daily committee.
- Regulatory vs family office unit standards—comparing across entities without metadata.
- Standard friction unit (bps/day) not yet in manifest—spiderweb integration open.
- Optimal rolling window length (126 vs 252 vs 504 days) for family office with quarterly rebalance.
- AI-driven market structure may change intraday correlation vs daily risk models.
- Whether to express spiderweb edge weights as correlation only or correlation divided by friction-adjusted capacity.

## Falsifiers

- One portfolio VaR number predicts binding limit breaches across all sleeves in 2020–2022 replay without sleeve-specific metrics.
- 252-day historical 95% 1d VaR breaches more than 8% of days on 60/40 walk-forward 2010–2025.
- Portfolio delta-equivalent alone predicts 1-week P&L within 10% RMSE on book with active options overlay.
- Single covariance-matrix VaR equals full-reval scenario ES within 5% on book with rates options and alts marks.
- Level 1 ES with metadata predicts IPS breach before weight-based monitor on 2020–2022 replay.
- One portfolio VaR number predicts binding limit breaches across all sleeves in 2020–2022 replay without sleeve-specific metrics.
- Equal-vol-weighted multi-asset basket shows equal max drawdown contributions across sleeves 2000–2025.
- 252-day historical 95% 1d VaR breaches more than 8% of days on 60/40 walk-forward 2010–2025.
- Portfolio delta-equivalent alone predicts 1-week P&L within 10% RMSE on book with active options overlay.
- ERC portfolio shows lower realized vol than cap-weight with equal 20y CAGR on multi-asset liquid basket.
- Single covariance-matrix VaR equals full-reval scenario ES within 5% on book with rates options and alts marks.
- Shops reporting daily 99% VaR show lower realized tail loss frequency than shops using stress scenarios only.
- Level 1 ES with metadata predicts IPS breach before weight-based monitor on 2020–2022 replay.
- 252-day historical 95% VaR breaches more than 8% of days on 60/40 portfolio 2010–2025 walk-forward.
- DCC-GARCH correlation forecast predicts next crisis cross-asset correlation matrix within 10% element-wise error.
- Friction-adjusted spiderweb routing improves risk-adjusted returns versus unadjusted correlation graph on walk-forward multi-asset books.

## Source Basis

- `risk-measurement-unit-framework`
- `volatility-variance-risk-unit`
- `dollar-tail-risk-units`
- `factor-sensitivity-risk-units`
- `risk-contribution-budget-units`
- `multi-asset-risk-unit-aggregation`
- `risk-measurement-disconfirming`
- `risk-unit-hierarchy-checklist`
- `simple-risk-models-historical-stress`
- `multi-asset-correlation-regime-risk`
- `financial-friction-logistics-cost`

## Next Questions

### Follow-Up — investigate next

1. What observable test, dataset, or experiment would most reduce the uncertainty that regime-conditional unit conversion (β to $ loss) breaks in crisis—stress units more honest than covariance units, and how far would resolving it move the current credence of 0.70? — This is the run's leading uncertainty driver, so settling it has the highest expected information value.
2. What concrete, pre-resolution indicator would let us monitor the falsifier 'One portfolio VaR number predicts binding limit breaches across all sleeves in 2020–2022 replay without sleeve-specific metrics' before 2026-07-03, rather than only learning the answer at resolution? — A falsifier you cannot observe in advance cannot guide updating, so operationalizing it turns the caveat into an actionable check.
3. Does the reference class behind '"Unit of risk" is not one number—it is a family of commensurate measures chosen for a decision: (A) volatility units (σ, annualized %), (B) dollar loss units (VaR, ES at horizon h), (C) sensitivity units per factor (β, DV01, Δ, Γ, vega), (D) risk contribution units (% of portfolio variance or ES), (E) liquidity-time units (days to liquidate at X% ADV)—multi-asset books require explicit mapping between units, never silent aggregation' condition on the same regime and scope as the target, and does re-stratifying it shift the prior? — A mis-specified reference class is a common source of miscalibrated base rates.

### What-If — negation probes

1. What if the supporting evidence reverses and 'Risk unit taxonomy (vol, dollar tail, factor sensitivity, risk contribution, liquidity-time); VaR ES drawdown; per-asset-class native units; multi-asset aggregation and commensurability; disconfirming false precision; recommended unit hierarchy for family office; follow-on to portfolio-risk-management-2026' instead fails before 2026-07-03? — Negating the prevailing lean (credence 0.70); pricing the disconfirming regime as the base case can reveal a hedge or contrarian edge the current view suppresses.
2. What if we treated the routing guardrail — '¬RM6 — What if risks are correlated, not independent? (Systemic risk, 2008-style contagion)' — as the opportunity rather than the thing to avoid? — Heuristic Algebra negation of the active heuristic surfaces paths the default routing suppresses by design.

### Open Sub-Questions — from sources

- Canonical risk manifest schema: {unit_type, horizon, confidence, currency, mark_source} per metric?
- Standard vol unit per sleeve in dashboard: 20d realized vs 60d EWMA?
- Report VaR and ES side-by-side with explicit (α, h) in InvestmentWarehouse risk panel?
- Minimum greek set per sleeve in unified risk manifest?
- Rebalance trigger on risk contribution drift vs weight drift—which unit binds first?
- Pre-registered stress pack as primary aggregator with covariance VaR as sanity check only?
- Minimum disclosure: {unit, α, h, window, mark_date} on every risk metric?
- Implement risk_unit_schema in warehouse dashboard API from this hierarchy?
- Pre-register simple stress pack (2008/2020/2022) in research sandbox config hash?
- Pre-registered stress pack for 2026–2031: inflation, deflation, stagflation, soft landing?
- Standard friction unit per lane (bps of notional per day) in Silk machine-readable manifest?
