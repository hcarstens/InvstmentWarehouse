# Portfolio Manager Workout

End-to-end run of the Investment Warehouse decision stack, driven from the **Portfolio Manager** tier. For each synthetic household the harness generates a portfolio and an IPS, packages them as a `pm.advise` process message, and dispatches it through the live messaging coordinator. The PM fans the working set out to the specialist legs (risk → policy → optimizer → attribution → tax) and returns one immutable `AdviceBundle` — the report and the recommendation.

- **As-of:** 2026-06-30
- **Seed:** 42 (deterministic, replayable)
- **Dispatch:** `op=pm.advise` · `kind=EVALUATE` (pure, no mutation)
- **Persona lens:** [Persona of The Portfolio Manager](docs/heuristics/Persona%20of%20The%20Portfolio%20Manager.md) — the 7-axiom ℍ_Allocation diagnostic
- **Households run:** 4 (one per HNW cohort)

## Run ledger

| Cohort | Household | NAV | Risk vol | Stress worst | TLH trades | Tax Δ | Drift alerts | Conc. alerts | PM headline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| general_hnw | `synthetic-general_hnw-s42` | $10,000,000 | 12.17% | -26.41% | 0 | 0.00 | 4 | 2 | 3 axiom breach(es) — whole-book review required |
| uhnw_inherited | `synthetic-uhnw_inherited-s42` | $10,000,000 | 14.67% | -26.55% | 0 | 0.00 | 6 | 2 | 2 axiom breach(es) — whole-book review required |
| founder_executive | `synthetic-founder_executive-s42` | $10,000,000 | 13.52% | -30.65% | 0 | 0.00 | 1 | 1 | 3 axiom breach(es) — whole-book review required |
| concentrated_stress | `synthetic-concentrated_stress-s42` | $10,000,000 | 13.97% | -32.98% | 1 | 0.00 | 1 | 1 | 3 axiom breach(es) — whole-book review required |

---

## general_hnw — `synthetic-general_hnw-s42`

NAV **$10,000,000** · rung 3 · correlation_id `pm-workout-general_hnw` · IPS `ips_synthetic-general_hnw-s42_v1` (v1, eff. 2024-01-15)

### 1 · Synthetic portfolio vs IPS policy

_Portfolio wt is the asset_portfolio manifest (incl. alternatives sub-ledger); the IPS drift column is computed on **lot positions only**, so alternatives held outside the lot ledger read as 0% and the lot denominator differs._

| Asset class | Portfolio wt | IPS target | Band | Lot drift |
| --- | --- | --- | --- | --- |
| alternatives | 8.20% | 8.20% | 3.20%–13.20% | -8.20% |
| cash | 8.79% | 8.79% | 3.79%–13.79% | 0.79% |
| equity | 65.56% | 65.56% | 60.56%–70.56% | 5.86% |
| fixed_income | 17.44% | 17.44% | 12.44%–22.44% | 1.56% |

IPS constraints: single-name concentration limit **12.00%**; min liquid (tier 1–2) **75.00%**; turnover budget **15.00%**.

### 2 · Risk report (whole-book)

- Annualized volatility: **12.17%**
- Expected return: **31.45%**
- Parametric VaR: 13.32% · ES: 32.17%
- Dollar VaR: $1,331,600 · Dollar ES: $3,217,328

Variance contribution by class (effective bets ≈ 1.38):

| Class | Weight | Ann. vol | % variance | % ES |
| --- | --- | --- | --- | --- |
| equity | 65.56% | 16.00% | 83.59% | 83.59% |
| alternatives | 8.20% | 33.75% | 16.55% | 16.55% |
| cash | 8.79% | 1.00% | 0.01% | 0.01% |
| fixed_income | 17.44% | 6.00% | -0.15% | -0.15% |

Stress replay (named scenarios):

| Scenario | Portfolio return |
| --- | --- |
| 2008_liquidity | -26.41% |
| 2020_pandemic | -22.70% |
| 2022_inflation | -20.00% |

### 3 · Recommendation (optimizer)

TLH / rebalance trades: **0** · estimated tax Δ: **0.00** · binding constraints: 3

_No tax-loss / rebalance trades proposed at this seed._

Binding constraints: `ips_max:equity`, `ips_min:alternatives`, `no_action:constraints_or_no_loss_lots`

**MV rebalance (advisory w\*)** — turnover L1 0.1566 · μ source `ex_ante_class_assumption` · stress regime `high_risk` · regime gap 0.0000

| Sleeve | Target w\* | Stress w\* |
| --- | --- | --- |
| equity | 63.59% | 63.59% |
| fixed_income | 21.05% | 21.05% |
| cash | 12.16% | 12.16% |
| alternatives | 3.20% | 3.20% |

Binding IPS bounds on w\*: `ips_min:alternatives`

### 4 · Policy monitoring (IPS drift)

**Allocation-band alerts:**
- alternatives below min (0.0% < 3.2%)
- alternatives drift 8.2% from target 8.2%
- equity above max (71.4% > 70.6%)
- equity drift 5.9% from target 65.6%

**Concentration alerts:**
- VTI concentration 71.4% (limit 12.0%)
- BND concentration 19.0% (limit 12.0%)

### 5 · Tax overlay

Scenario tax Δ: **0.00** (NIIT/AMT overlay seam wired; estimate deferred — honesty axiom #5 stays `not_computed`).

### 6 · Attribution

Per-position attribution: **3** positions · portfolio active return **-9.13%** (MV-weighted) · config `2026.06`.

Limitations: Unrealized point-in-time only — no realized lots, income or dividends.; Class-beta first cut — not full factor (Brinson) attribution.; ETF maps to EQUITY as a v0 beta proxy; bond/commodity ETFs are mis-mapped until look-through ships.; The beta-stripped idiosyncratic component (axiom 1) is not_computed — no realized class-return series to subtract.

### 7 · Portfolio Manager diagnostic (ℍ_Allocation 7-axiom)

**Headline:** 3 axiom breach(es) — whole-book review required

| Axiom | Score |
| --- | --- |
| 1 · Portfolio is the unit of account (risk measured) | `pass` |
| 2 · Diversification — effective bets | `breach` |
| 3 · Position sizing / concentration | `breach` |
| 4 · Survive to compound (stress tails) | `warn` |
| 5 · Margin of safety (deferred) | `not_computed` |
| 6 · Control exposure (binding constraints) | `pass` |
| 7 · Rebalance on calibrated evidence (drift) | `breach` |

Specialist legs: analyst=`live`, optimizer=`live`, risk=`live`, tax=`stub`

---

## uhnw_inherited — `synthetic-uhnw_inherited-s42`

NAV **$10,000,000** · rung 3 · correlation_id `pm-workout-uhnw_inherited` · IPS `ips_synthetic-uhnw_inherited-s42_v1` (v1, eff. 2024-01-15)

### 1 · Synthetic portfolio vs IPS policy

_Portfolio wt is the asset_portfolio manifest (incl. alternatives sub-ledger); the IPS drift column is computed on **lot positions only**, so alternatives held outside the lot ledger read as 0% and the lot denominator differs._

| Asset class | Portfolio wt | IPS target | Band | Lot drift |
| --- | --- | --- | --- | --- |
| alternatives | 22.58% | 22.58% | 17.58%–27.58% | -22.58% |
| cash | 6.78% | 6.78% | 1.78%–11.78% | 1.98% |
| commodities | 7.11% | 7.11% | 2.11%–12.11% | -7.11% |
| equity | 49.41% | 49.41% | 44.41%–54.41% | 23.59% |
| fixed_income | 14.13% | 14.13% | 9.13%–19.13% | 4.12% |

IPS constraints: single-name concentration limit **10.00%**; min liquid (tier 1–2) **55.00%**; turnover budget **12.00%**.

### 2 · Risk report (whole-book)

- Annualized volatility: **14.67%**
- Expected return: **33.07%**
- Parametric VaR: 20.87% · ES: 43.59%
- Dollar VaR: $2,086,724 · Dollar ES: $4,359,091

Variance contribution by class (effective bets ≈ 2.32):

| Class | Weight | Ann. vol | % variance | % ES |
| --- | --- | --- | --- | --- |
| equity | 49.41% | 16.00% | 46.31% | 46.31% |
| alternatives | 22.58% | 33.75% | 46.02% | 46.02% |
| commodities | 7.11% | 27.00% | 6.98% | 6.98% |
| fixed_income | 14.13% | 6.00% | 0.69% | 0.69% |
| cash | 6.78% | 1.00% | 0.00% | 0.00% |

Stress replay (named scenarios):

| Scenario | Portfolio return |
| --- | --- |
| 2008_liquidity | -26.55% |
| 2020_pandemic | -22.63% |
| 2022_inflation | -16.01% |

### 3 · Recommendation (optimizer)

TLH / rebalance trades: **0** · estimated tax Δ: **0.00** · binding constraints: 4

_No tax-loss / rebalance trades proposed at this seed._

Binding constraints: `ips_max:equity`, `ips_min:alternatives`, `ips_min:commodities`, `no_action:constraints_or_no_loss_lots`

**MV rebalance (advisory w\*)** — turnover L1 0.3938 · μ source `ex_ante_class_assumption` · stress regime `high_risk` · regime gap 0.0010

| Sleeve | Target w\* | Stress w\* |
| --- | --- | --- |
| equity | 54.41% | 54.41% |
| alternatives | 17.58% | 17.58% |
| fixed_income | 17.47% | 17.43% |
| cash | 8.43% | 8.48% |
| commodities | 2.11% | 2.11% |

Binding IPS bounds on w\*: `ips_max:equity`, `ips_min:commodities`, `ips_min:alternatives`

### 4 · Policy monitoring (IPS drift)

**Allocation-band alerts:**
- alternatives below min (0.0% < 17.6%)
- alternatives drift 22.6% from target 22.6%
- commodities below min (0.0% < 2.1%)
- commodities drift 7.1% from target 7.1%
- equity above max (73.0% > 54.4%)
- equity drift 23.6% from target 49.4%

**Concentration alerts:**
- VTI concentration 63.8% (limit 10.0%)
- BND concentration 18.2% (limit 10.0%)

### 5 · Tax overlay

Scenario tax Δ: **0.00** (NIIT/AMT overlay seam wired; estimate deferred — honesty axiom #5 stays `not_computed`).

### 6 · Attribution

Per-position attribution: **4** positions · portfolio active return **-9.63%** (MV-weighted) · config `2026.06`.

Limitations: Unrealized point-in-time only — no realized lots, income or dividends.; Class-beta first cut — not full factor (Brinson) attribution.; ETF maps to EQUITY as a v0 beta proxy; bond/commodity ETFs are mis-mapped until look-through ships.; The beta-stripped idiosyncratic component (axiom 1) is not_computed — no realized class-return series to subtract.

### 7 · Portfolio Manager diagnostic (ℍ_Allocation 7-axiom)

**Headline:** 2 axiom breach(es) — whole-book review required

| Axiom | Score |
| --- | --- |
| 1 · Portfolio is the unit of account (risk measured) | `pass` |
| 2 · Diversification — effective bets | `warn` |
| 3 · Position sizing / concentration | `breach` |
| 4 · Survive to compound (stress tails) | `warn` |
| 5 · Margin of safety (deferred) | `not_computed` |
| 6 · Control exposure (binding constraints) | `warn` |
| 7 · Rebalance on calibrated evidence (drift) | `breach` |

Specialist legs: analyst=`live`, optimizer=`live`, risk=`live`, tax=`stub`

---

## founder_executive — `synthetic-founder_executive-s42`

NAV **$10,000,000** · rung 3 · correlation_id `pm-workout-founder_executive` · IPS `ips_synthetic-founder_executive-s42_v1` (v1, eff. 2024-01-15)

### 1 · Synthetic portfolio vs IPS policy

_Portfolio wt is the asset_portfolio manifest (incl. alternatives sub-ledger); the IPS drift column is computed on **lot positions only**, so alternatives held outside the lot ledger read as 0% and the lot denominator differs._

| Asset class | Portfolio wt | IPS target | Band | Lot drift |
| --- | --- | --- | --- | --- |
| alternatives | 6.00% | 6.00% | 0.00%–14.00% | -6.00% |
| cash | 8.08% | 8.08% | 0.08%–16.08% | 0.52% |
| equity | 77.26% | 77.26% | 69.26%–85.26% | 4.93% |
| fixed_income | 8.66% | 8.66% | 0.66%–16.66% | 0.55% |

IPS constraints: single-name concentration limit **17.00%**; min liquid (tier 1–2) **70.00%**; turnover budget **20.00%**.

### 2 · Risk report (whole-book)

- Annualized volatility: **13.52%**
- Expected return: **32.69%**
- Parametric VaR: 17.04% · ES: 38.00%
- Dollar VaR: $1,704,489 · Dollar ES: $3,799,592

Variance contribution by class (effective bets ≈ 1.21):

| Class | Weight | Ann. vol | % variance | % ES |
| --- | --- | --- | --- | --- |
| equity | 77.26% | 16.00% | 90.42% | 90.42% |
| alternatives | 6.00% | 33.75% | 9.95% | 9.95% |
| cash | 8.08% | 1.00% | 0.00% | 0.00% |
| fixed_income | 8.66% | 6.00% | -0.38% | -0.38% |

Stress replay (named scenarios):

| Scenario | Portfolio return |
| --- | --- |
| 2008_liquidity | -30.65% |
| 2020_pandemic | -26.90% |
| 2022_inflation | -21.38% |

### 3 · Recommendation (optimizer)

TLH / rebalance trades: **0** · estimated tax Δ: **0.00** · binding constraints: 0

_No tax-loss / rebalance trades proposed at this seed._

**MV rebalance (advisory w\*)** — turnover L1 0.2000 · μ source `ex_ante_class_assumption` · stress regime `high_risk` · regime gap 0.0309

| Sleeve | Target w\* | Stress w\* |
| --- | --- | --- |
| equity | 72.20% | 72.20% |
| fixed_income | 14.97% | 13.42% |
| cash | 12.84% | 14.38% |
| alternatives | 0.00% | 0.00% |

Binding IPS bounds on w\*: `ips_min:alternatives`

### 4 · Policy monitoring (IPS drift)

**Allocation-band alerts:**
- alternatives drift 6.0% from target 6.0%

**Concentration alerts:**
- VTI concentration 82.2% (limit 17.0%)

### 5 · Tax overlay

Scenario tax Δ: **0.00** (NIIT/AMT overlay seam wired; estimate deferred — honesty axiom #5 stays `not_computed`).

### 6 · Attribution

Per-position attribution: **3** positions · portfolio active return **-8.57%** (MV-weighted) · config `2026.06`.

Limitations: Unrealized point-in-time only — no realized lots, income or dividends.; Class-beta first cut — not full factor (Brinson) attribution.; ETF maps to EQUITY as a v0 beta proxy; bond/commodity ETFs are mis-mapped until look-through ships.; The beta-stripped idiosyncratic component (axiom 1) is not_computed — no realized class-return series to subtract.

### 7 · Portfolio Manager diagnostic (ℍ_Allocation 7-axiom)

**Headline:** 3 axiom breach(es) — whole-book review required

| Axiom | Score |
| --- | --- |
| 1 · Portfolio is the unit of account (risk measured) | `pass` |
| 2 · Diversification — effective bets | `breach` |
| 3 · Position sizing / concentration | `breach` |
| 4 · Survive to compound (stress tails) | `warn` |
| 5 · Margin of safety (deferred) | `not_computed` |
| 6 · Control exposure (binding constraints) | `pass` |
| 7 · Rebalance on calibrated evidence (drift) | `breach` |

Specialist legs: analyst=`live`, optimizer=`live`, risk=`live`, tax=`stub`

---

## concentrated_stress — `synthetic-concentrated_stress-s42`

NAV **$10,000,000** · rung 4 · correlation_id `pm-workout-concentrated_stress` · IPS `ips_synthetic-concentrated_stress-s42_v1` (v1, eff. 2024-01-15)

### 1 · Synthetic portfolio vs IPS policy

_Portfolio wt is the asset_portfolio manifest (incl. alternatives sub-ledger); the IPS drift column is computed on **lot positions only**, so alternatives held outside the lot ledger read as 0% and the lot denominator differs._

| Asset class | Portfolio wt | IPS target | Band | Lot drift |
| --- | --- | --- | --- | --- |
| cash | 6.75% | 6.75% | 4.75%–8.75% | 0.00% |
| equity | 87.69% | 87.19% | 85.19%–87.19% | 0.50% |
| fixed_income | 5.56% | 5.56% | 3.56%–7.56% | 0.00% |

IPS constraints: single-name concentration limit **21.00%**; min liquid (tier 1–2) **60.00%**; turnover budget **10.00%**.

### 2 · Risk report (whole-book)

- Annualized volatility: **13.97%**
- Expected return: **32.82%**
- Parametric VaR: 18.56% · ES: 40.20%
- Dollar VaR: $1,855,618 · Dollar ES: $4,019,817

Variance contribution by class (effective bets ≈ 0.99):

| Class | Weight | Ann. vol | % variance | % ES |
| --- | --- | --- | --- | --- |
| equity | 87.69% | 16.00% | 100.42% | 100.42% |
| cash | 6.75% | 1.00% | 0.00% | 0.00% |
| fixed_income | 5.56% | 6.00% | -0.42% | -0.42% |

Stress replay (named scenarios):

| Scenario | Portfolio return |
| --- | --- |
| 2008_liquidity | -32.98% |
| 2020_pandemic | -29.37% |
| 2022_inflation | -22.89% |

### 3 · Recommendation (optimizer)

TLH / rebalance trades: **1** · estimated tax Δ: **-38971.96** · binding constraints: 1

| Side | Qty | Security | Rationale |
| --- | --- | --- | --- |
| sell | 6495.33 | `AAPL` | TLH harvest unrealized loss -194859.80 (AAPL, est tax delta -38971.96) |

Binding constraints: `ips_max:equity`

**MV rebalance (advisory w\*)** — turnover L1 0.0500 · μ source `ex_ante_class_assumption` · stress regime `high_risk` · regime gap 0.0300

| Sleeve | Target w\* | Stress w\* |
| --- | --- | --- |
| equity | 85.19% | 85.19% |
| fixed_income | 7.56% | 6.06% |
| cash | 7.25% | 8.75% |

Binding IPS bounds on w\*: `ips_min:equity`, `ips_max:fixed_income`

### 4 · Policy monitoring (IPS drift)

**Allocation-band alerts:**
- equity above max (87.7% > 87.2%)

**Concentration alerts:**
- VTI concentration 52.6% (limit 21.0%)

### 5 · Tax overlay

Scenario tax Δ: **0.00** (NIIT/AMT overlay seam wired; estimate deferred — honesty axiom #5 stays `not_computed`).

### 6 · Attribution

Per-position attribution: **6** positions · portfolio active return **-30.87%** (MV-weighted) · config `2026.06`.

Limitations: Unrealized point-in-time only — no realized lots, income or dividends.; Class-beta first cut — not full factor (Brinson) attribution.; ETF maps to EQUITY as a v0 beta proxy; bond/commodity ETFs are mis-mapped until look-through ships.; The beta-stripped idiosyncratic component (axiom 1) is not_computed — no realized class-return series to subtract.

### 7 · Portfolio Manager diagnostic (ℍ_Allocation 7-axiom)

**Headline:** 3 axiom breach(es) — whole-book review required

| Axiom | Score |
| --- | --- |
| 1 · Portfolio is the unit of account (risk measured) | `pass` |
| 2 · Diversification — effective bets | `breach` |
| 3 · Position sizing / concentration | `breach` |
| 4 · Survive to compound (stress tails) | `warn` |
| 5 · Margin of safety (deferred) | `not_computed` |
| 6 · Control exposure (binding constraints) | `pass` |
| 7 · Rebalance on calibrated evidence (drift) | `breach` |

Specialist legs: analyst=`live`, optimizer=`live`, risk=`live`, tax=`stub`

---

## How the stack was driven

1. **Generate portfolio** — `emit_synthetic_household(cohort, seed, rung)` emits a Shape-B fixture (accounts, lots, alternatives, asset-class manifest) sized to the cohort sleeve ranges.
2. **Generate IPS** — co-generated in the same call: allocation targets with min/max bands, concentration limit, restricted names, validated against the fixture.
3. **Process message** — `build_working_set_from_bundle(...)` slices `{positions, ips, manifest, risk request}` into a `PmAdvisePayload`, wrapped in a `Message(op="pm.advise", kind=EVALUATE)`.
4. **Dispatch from the PM** — `dispatch_typed(ctx, msg, AdviceBundle)` routes through `warehouse.messaging.core`; the `pm.advise` coordinator nest-dispatches each specialist leg under the same `correlation_id`.
5. **Result** — one frozen `AdviceBundle` carrying the risk report, the optimizer recommendation (TLH trades + MV rebalance), the tax scenario, the IPS drift report, attribution, and the PM narrative.

Re-run: `python scratchpad/pm_workout.py` (in-process, no database, no external services).
