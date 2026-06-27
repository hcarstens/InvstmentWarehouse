# Portfolio Optimization for Multi-Asset Portfolios

Multi-asset portfolio optimization selects a **weight vector** **w** (or trade vector **Δw**) across equities, rates, commodities, FX, and alternatives subject to IPS bounds, liquidity, and risk budget. Family offices prioritize **after-tax utility** and **policy tracking** over unconstrained max-Sharpe.

Related: [ips.md](ips.md) (IPS governance), [portfolio_risk.md](portfolio_risk.md) (risk measurement), [rebalancing.md](rebalancing.md) (rebalance rules), [simple_risk_models.md](simple_risk_models.md) (covariance / VaR stack).

---

## Optimization Math

Multi-asset portfolio optimization is a constrained program over vectors in **Rⁿ** (with mixed-integer extensions for lot-level decisions).

### Mean-variance (QP)

**Maximize:** `w'μ − (λ/2) w'Σw`

**Subject to:**
- `1'w = 1` (fully invested)
- `w_min ≤ w ≤ w_max` (IPS sleeve bounds)
- `Aw ≤ b` (concentration, liquidity, turnover `||Δw||₁ ≤ τ`)

Unconstrained closed form: `w* ∝ Σ⁻¹(μ − λ1)`. With IPS bounds this becomes a **quadratic program (QP)**.

### Portfolio risk decomposition

| Quantity | Formula | Role |
| --- | --- | --- |
| Portfolio variance | `σ_p² = w'Σw` | Risk objective / constraint |
| Marginal contribution | `MC_i = w_i (Σw)_i` | Sensitivity of variance to sleeve *i* |
| Risk contribution share | `RC_i = MC_i / σ_p²` | Sums to 100%; rebalance in **risk space** |

### Alternative objectives

- **Tracking error:** `(w − w_policy)'Σ(w − w_policy)` vs IPS benchmark
- **Risk budget / ERC:** target equal or fixed `RC_i`
- **After-tax utility:** effective `μ_after-tax` with lot binaries `x_l` → **MIQP/MIP**
- **Scenario robust:** shock vector **s** on factor sensitivities → $ P&L distribution (preferred when Σ breaks in crisis)

### Solver tiers

| Problem | Solver |
| --- | --- |
| Constrained MV | QP |
| Robust / uncertainty sets | SOCP |
| Lot discreteness + wash-sale graph | MIQP/MIP (Gurobi, CPLEX) |
| Family office v0 | TLH heuristics + greedy rebalance → MIP upgrade path |

---

## Optimization Vectors

| Vector | Definition | Use |
| --- | --- | --- |
| **w** | Sleeve/asset weights, `Σw_i = 1` | Decision variable / state |
| **Δw** | `w_target − w_current` | Rebalance trades |
| **d** (drift) | `w_current − w_policy` | IPS breach magnitude; triggers optimizer |
| **μ** | Expected returns by sleeve | Objective input (ERP, term premium, carry, roll yield) |
| **Σ** | Covariance matrix (block by asset class) | Risk objective; walk-forward estimated |
| **RC** | Risk contribution shares | Risk-budget rebalance trigger |
| **x_l** | Lot sell/hold binaries | After-tax MIP |
| **s** | Scenario shock vector | Stress / tail aggregation |
| Account placement | Which sleeve in taxable vs IRA vs trust | Asset location layer |

**InvestmentWarehouse today:**
- **Risk plane** (`portfolio_covariance`): computes `w'Σw`, marginal variance, `pct_variance_contributions` from `AllocationSlot` weights
- **Decision plane** (optimizer v0): TLH ranking + IPS min/max on class weights — not full MV QP yet

---

## Multi-Asset Specifics

1. **Σ is regime-conditional** — static 60/40 Σ failed in 2022; complement MV with stress scenarios (equity −30%, rates +200bp, oil +40%, USD +10%).

2. **Weight ≠ risk** — HY and IG at same weight have different `RC_i`; IPS % NAV limits must map to risk units.

3. **Native sensitivity units per sleeve** — beta ($/1% equity move), DV01 ($/bp), greeks, FX delta — aggregate only approximately to a common dollar unit.

4. **Risk-budget vs weight rebalance diverge** — 2022 risk parity bought bonds / sold equities, opposite to naive contrarian weight rebalance.

5. **Illiquid sleeves** (PE, real estate) sit outside daily **Δw** — optimize liquid **w** conditional on liquidity ladder and committed capital.

6. **μ estimation error** often dominates MV theory — equal-weight or static IPS policy weights are often competitive OOS net of turnover.

---

## Objective Hierarchy (Family Office)

1. After-tax wealth / utility
2. Tracking error vs IPS policy benchmark
3. Risk parity / ERC targets
4. Turnover and tax cost penalties

Tax overlays (TLH, asset location, gain deferral) run **inside** IPS hard bounds, not as a substitute.

---

## Failure Modes

- Stale **μ** and **Σ** → unstable optima
- Pre-tax MV on after-tax mandate
- Options linearized in **Σ** while gamma matters
- Illiquids treated as daily-rebalance assets
- Weight-only books → no lot-level after-tax optimization
- Covariance VaR diverges from scenario ES on options + alts books

---

## DHA Research Run

*DHA research run `multi-asset-portfolio-optimization-2026` · 2026-06-28 · credence 0.70 · quality 10/10*

Config: `DHAResearchAgent/configs/multi_asset_portfolio_optimization_20260628.json`

---

## DHA Domain Writer Summary

<!-- source: DHAResearchAgent/runs/research/multi-asset-portfolio-optimization-2026/20260628T120000Z0000/domain_writer/summary.md -->

# Portfolio optimization for multi-asset portfolios

Run status: `complete`

Research quality score: `10/10`

## Bottom Line

Synthesis for 'Portfolio optimization for multi-asset portfolios': 95 supporting claim(s), 32 disconfirming claim(s); deterministic credence 0.696. 14 open sub-question(s) recorded.

## Base Rates

- Multi-asset portfolio optimization is formulated over vectors in R^n (or mixed-integer extensions): weight vector w, expected return vector μ, covariance matrix Σ, trade vector Δw, and constraint bounds from IPS—family office implementations add lot-level binary vectors and after-tax effective return vectors.
- Multi-asset portfolio optimization selects weight vector w (or trade vector Δw) across equities, rates, commodities, FX, and alternatives subject to IPS bounds, liquidity, and risk budget—family offices prioritize after-tax utility and policy tracking over unconstrained max-Sharpe.
- Multi-asset portfolio optimizers fail when Σ and μ are stale, options are linearized, illiquids are treated as daily-rebalance assets, or pre-tax MV is applied to after-tax mandates—demo optima breach limits in pilot.
- Tax-aware investment optimization at family offices combines (1) after-tax return expectations, (2) lot-level trade constraints, (3) multi-account asset location, and (4) household-level tax bracket dynamics—typically solved as constrained optimization or heuristic trade-priority rules when full MIP is too slow.
- Multi-asset portfolio risk is regime-conditional—correlations compress toward +1 in liquidity crises (2008, 2020, 2022)—risk management requires stress scenarios and correlation shocks, not one historical covariance matrix.
- Multi-asset risk measurement fails when unlike units are summed without bridge—correct aggregation paths: (1) simulate joint scenarios → single $ P&L distribution; (2) covariance matrix on synchronized return series → portfolio σ and VaR; (3) report sleeve-native units side-by-side without false total—illiquids get liquidity-time unit not daily VaR.
- Risk budgeting uses unit of marginal contribution: each sleeve's % of total portfolio variance (or ES)—sums to 100%; equal risk contribution (ERC) targets equal % from each sleeve—unit is dimensionless share of total risk not dollar or σ alone.
- Portfolio risk models decompose into (1) exposure measurement (positions × sensitivities), (2) covariance/volatility estimation, (3) aggregation (linear factor, full revaluation, simulation), (4) tail metrics (VaR, ES, stress P&L), (5) attribution and reconciliation—family office failure concentrates in stale covariance, linearizing options, and monthly marks on illiquid alts.
- Each asset class has native sensitivity units measuring $ P&L per unit move in risk factor—equities: beta ($ per 1% index move); rates: DV01 ($ per 1bp parallel shift); options: delta ($ per $1 underlying), gamma ($ per $1²), vega ($ per 1 vol point); FX: delta per 1% spot; commodities: $ per $1 or per tick—portfolio risk measurement aggregates these to common dollar delta-equivalents only approximately.
- Risk-budget rebalancing adjusts positions when risk contributions drift—not raw weights—after a run-up with rising vol, the asset may be trimmed even if return momentum positive; after drawdown with vol spike, trim may be larger (vol targeting) or smaller (if correlation drops)—direction differs from naive buy-drawdown/sell-runup.
- Multi-asset portfolio risk management decomposes into (1) risk measurement, (2) risk budgeting/allocation, (3) tail and liquidity risk, (4) instrument-specific factor exposures, (5) hedging and overlays, (6) governance and limits—with failure most often from stale correlations, illiquid marks, and options gamma ignored until expiry week.
- Over a five-year horizon (2026–2031), implementable alpha in liquid markets clusters in risk premia (carry, term premium, equity premium), slow-moving mispricings (FX valuation, curve shape), episodic dislocations (commodity supply shocks), and crypto-native flows—not in republished daily momentum on ES or BTC without friction adjustment.
- Family office rebalance is paired trim-overweight / fund-underweight on IPS drift—drawdown assets often bought, run-up assets trimmed—with tax asymmetry: harvest drawdown substitutes first, defer trimming run-up winners in taxable accounts until drift forces.
- InvestmentWarehouse is a tech-enabled multi-family office platform shell implementing Sharpe brief priorities—after-tax north star, five operational planes, six workflows—dashboard-first with `warehouse serve` as living status report.

## Uncertainty Drivers

- Factor model Σ (few factors) vs full asset Σ for n > 50 liquid sleeves—bias-variance tradeoff in multi-asset allocator.
- LLM factor crowding compresses implementable μ for published sleeves—optimizer inputs decay faster post-2024.
- Crypto sleeve: α decomposes into BTC beta—μ vector must hedge latent beta or optimization loads wrong risk.
- AI market structure may invalidate daily Σ for intraday options books.
- Sharpe may target planning/simulation ("what if we move to TX and harvest $2M losses") more than daily auto-TLH like robo-advisors.
- AI-driven market structure may change intraday correlation vs daily risk models.
- AI intraday structure may require hourly risk unit for options books vs daily committee.
- After-tax risk contribution (harvesting changes weights) rarely computed—pre-tax unit only in practice.
- LLM-accelerated factor crowding shortens half-life of published factor covariance estimates.
- Private equity reported beta to public markets is unstable—sensitivity unit noisy.
- Short vol vs long vol regime changes risk-parity rebalance direction quarterly.
- LLM-accelerated factor crowding compresses hedge effectiveness on published risk premia sleeves.
- Whether 2026–2031 is disinflationary grind, reflation spike, or stagnation—rank order of asset classes is regime-conditional.
- TCJA sunset re-sorts deferral vs harvest priority 2028+.
- Heuristic agents and report writer integration with dashboard and approval gates—in TODO open questions.

## Falsifiers

- Unconstrained MV optimum on rolling 252d Σ beats equal-weight 60/40 on OOS Sharpe 2000–2025 after turnover costs.
- Constrained MV on walk-forward Σ beats risk-budget ERC on max drawdown 2000–2025 multi-asset liquid basket net of costs.
- Static 60/40 correlation matrix Σ produces optimizer hedge ratios within 1σ of realized 2022 joint drawdown.
- Constrained MV optimizer beats static IPS policy weights on after-tax Calmar 2015–2025 multi-asset family book with realistic turnover.
- Single covariance-matrix VaR equals full-reval scenario ES within 5% on book with rates options and alts marks.
- Unconstrained MV optimum on rolling 252d Σ beats equal-weight 60/40 on OOS Sharpe 2000–2025 after turnover costs.
- Constrained MV on walk-forward Σ beats risk-budget ERC on max drawdown 2000–2025 multi-asset liquid basket net of costs.
- Constrained MV optimizer beats static IPS policy weights on after-tax Calmar 2015–2025 multi-asset family book with realistic turnover.
- Optimization framework that optimizes pre-tax Sharpe only while marketing tax-aware outcomes.
- DCC-GARCH correlation forecast predicts next crisis cross-asset correlation matrix within 10% element-wise error.
- Single covariance-matrix VaR equals full-reval scenario ES within 5% on book with rates options and alts marks.
- ERC portfolio shows lower realized vol than cap-weight with equal 20y CAGR on multi-asset liquid basket.
- Weight-only risk dashboard predicts binding constraint violations as well as full factor+greek stack on 2020–2022 replay.
- Portfolio delta-equivalent alone predicts 1-week P&L within 10% RMSE on book with active options overlay.
- Risk-budget rebalance fails to reduce max drawdown vs weight rebalance on 60/40 2000–2025.
- Static 60/40 correlation matrix risk model predicts 2022 bond-equity joint drawdown within 1σ band.
- Equal-risk passive basket across five asset classes matches top-quartile systematic alpha funds net of fees 2026–2031.
- Tax-agnostic rebalance beats tax-aware overlay on after-tax wealth 10y concentrated US equity family book.
- Dashboard panels show stub data while backend claims live reconciliation—violates dashboard-first rule.

## Source Basis

- `investmentwarehouse-optimization-math-context`
- `multi-asset-portfolio-optimization-framework`
- `multi-asset-portfolio-optimization-disconfirming`
- `sharpe-tax-optimization-framework`
- `multi-asset-correlation-regime-risk`
- `multi-asset-risk-unit-aggregation`
- `risk-contribution-budget-units`
- `risk-models-framework`
- `factor-sensitivity-risk-units`
- `rebalance-risk-budgeting`
- `portfolio-risk-management-framework`
- `cross-asset-alpha-5y-framework`
- `family-office-tax-rebalance`
- `investmentwarehouse-platform-context`

## Next Questions

### Follow-Up — investigate next

1. What observable test, dataset, or experiment would most reduce the uncertainty that factor model Σ (few factors) vs full asset Σ for n > 50 liquid sleeves—bias-variance tradeoff in multi-asset allocator, and how far would resolving it move the current credence of 0.70? — This is the run's leading uncertainty driver, so settling it has the highest expected information value.
2. What concrete, pre-resolution indicator would let us monitor the falsifier 'Unconstrained MV optimum on rolling 252d Σ beats equal-weight 60/40 on OOS Sharpe 2000–2025 after turnover costs' before 2026-06-28, rather than only learning the answer at resolution? — A falsifier you cannot observe in advance cannot guide updating, so operationalizing it turns the caveat into an actionable check.
3. Does the reference class behind 'Multi-asset portfolio optimization is formulated over vectors in R^n (or mixed-integer extensions): weight vector w, expected return vector μ, covariance matrix Σ, trade vector Δw, and constraint bounds from IPS—family office implementations add lot-level binary vectors and after-tax effective return vectors' condition on the same regime and scope as the target, and does re-stratifying it shift the prior? — A mis-specified reference class is a common source of miscalibrated base rates.

### What-If — negation probes

1. What if the supporting evidence reverses and 'Optimization math (μ, Σ, w, QP/MV, risk contributions, after-tax MIQP); optimization vectors (weight, trade, drift, risk contribution, lot binary, scenario P&L); multi-asset objectives and constraints; covariance vs scenario aggregation; risk-budget vs weight rebalance; IPS and tax overlays; solver tiers; InvestmentWarehouse risk API and optimizer mapping; disconfirming estimation and regime failures' instead fails before 2026-06-28? — Negating the prevailing lean (credence 0.70); pricing the disconfirming regime as the base case can reveal a hedge or contrarian edge the current view suppresses.
2. What if we treated the routing guardrail — '¬M1 — What if the system is irreducible? (Emergent properties, complexity)' — as the opportunity rather than the thing to avoid? — Heuristic Algebra negation of the active heuristic surfaces paths the default routing suppresses by design.

### Open Sub-Questions — from sources

- Unified optimization vector schema: w, Δw, RC, drift, scenario P&L in machine-readable manifest per household?
- Joint optimizer for w and hedge overlay variables or sequential (optimize w then hedge residual)?
- When to abandon MV for scenario-based robust optimization only—regime indicator trigger?
- Does Sharpe model AMT, NIIT, QSBS, and trust distributable net income in v0 or defer to external tax engine?
- Pre-registered stress pack for 2026–2031: inflation, deflation, stagflation, soft landing?
- Pre-registered stress pack as primary aggregator with covariance VaR as sanity check only?
- Rebalance trigger on risk contribution drift vs weight drift—which unit binds first?
- Minimum viable risk model stack for $50M family office without full vendor buy?
- Minimum greek set per sleeve in unified risk manifest?
- Publish joint rule: weight band OR risk band breach triggers rebalance— which binds first?
- Unified risk manifest per household: factor exposures × liquidity tier × mark cadence?
- Standard 5y alpha unit—bps Sharpe, IR, or Calmar per asset class at $100M capacity?
- Minimum IPS drift to justify realizing gains on run-up sleeve?
- Sync family-office consideration manifest to InvestmentWarehouse docs/research/ after each DHA run?
