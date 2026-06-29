# Software testing — framework, metrics, and tools

Run status: `complete`

Research quality score: `10/10`

## Bottom Line

Synthesis for 'Software testing — framework, metrics, and tools': 67 supporting claim(s), 22 disconfirming claim(s); deterministic credence 0.892. 10 open sub-question(s) recorded.

## Base Rates

- Mature software teams organize testing as a pyramid—many fast unit tests, fewer integration tests, and a thin layer of end-to-end tests—because unit tests give the best defect-detection cost ratio while E2E tests catch wiring failures but are slow and flaky.
- Effective test metrics combine code/process signals (coverage, pass rate) with outcome signals (defect escape rate, MTTR, deployment frequency)—coverage alone is insufficient because untested branches and meaningless assertions inflate scores without reducing production risk.
- Modern test stacks pair a language-native runner (pytest, Jest, Go test, Rust cargo test) with CI orchestration (GitHub Actions, GitLab CI), optional coverage reporters, and specialized layers for API, browser, load, and security testing—teams standardize on one runner per language and compose tools by test type.
- Software testing programs fail when metrics become targets (coverage gaming), flaky suites are tolerated, tests duplicate production logic, or slow gates are bypassed—green CI becomes false confidence while escape rate stays high.
- A backtest is referenceable only when another user can recover the exact data slice, code revision, random seed, and evaluation protocol that produced reported metrics.
- Credible backtesting scaffolding centers on rolling-origin or walk-forward evaluation where each cutoff sees only past data and future actuals are scored out-of-sample.
- HNW synthetic portfolio generation must satisfy SDG axioms with explicit acceptance tests per axiom—generation starts from portfolio domain rules (IPS, lots, liquidity, entity graph), not from marginal weight distributions alone.
- Synthetic daily paths must be validated against distributional checks (vol clustering, kurtosis, autocorrelation) and null baselines (shuffle, bootstrap) before trusting strategy test results.
- Any synthetic scenario used to test new FIIJ rules must pass walk-forward or cross-regime validation before deployment; sell-at-lows and size cuts on loss signals require 2022-2025 bear coverage.
- Multiuser forecasting teams need run records that bind code version, config, data snapshot, metrics, and artifacts so a backtest can be reproduced or extended later.

## Uncertainty Drivers

- AI-generated tests may inflate coverage without meaningful assertions—human review of assertion quality remains necessary.
- AI coding assistants may increase commit velocity faster than test authoring—escape rate may rise before teams adapt review gates.
- LLM test generators (Copilot tests, Codium) may shift burden from authoring to reviewing generated assertions.
- Whether AI-generated test suites will reduce or increase escape rate over 2026–2028 as adoption scales.
- How much of the rolling-origin split sequence must be serialized versus recomputable from config and dataset hash.
- Teams disagree on minimum train length, embargo length, and whether to store every split or only aggregate metrics.
- Downstream falsification benchmark—no public HNW lot-level dataset; may use synthetic-vs-synthetic holdout until pilot client anonymized panels exist.
- Acceptable tolerance for mismatch between synthetic and real sigma tier histograms in FIIJ OOS attribution.
- How to inject stablecoin flow and silk direction conjunction priors into purely synthetic crypto paths.
- Whether forecasting repos should adopt a heavyweight tracker or a git-native card catalog like research-run propagation.

## Falsifiers

- Teams with inverted test pyramid (mostly E2E) show lower production defect escape rate than pyramid-balanced teams at equal CI spend.
- 90% line coverage correlates with lower escape rate than 70% branch coverage plus mutation testing on core modules.
- Five overlapping commercial test suites reduce escape rate versus pytest plus Playwright plus GitHub Actions at equal headcount.
- Flaky test quarantine without fix increases merge velocity without increasing production incident rate.
- AI-generated unit tests without human assertion review match human-authored tests on mutation kill rate.
- Teams with inverted pyramid (mostly E2E) ship fewer production defects per commit than teams with 70%+ unit test share at equal total CI minutes.
- Teams above 90% line coverage show lower production defect escape rate than teams at 60–80% branch coverage on mutation-tested core modules, holding deploy frequency constant.
- Teams using Playwright + pytest + GitHub Actions alone match defect escape rate of teams running five overlapping commercial suites at equal engineer headcount.
- Mutation score >80% on core modules fails to predict lower sev-1/2 escape rate than branch coverage alone over 12-month cohort.
- Independent teams reproduce published backtest metrics from card metadata alone without access to private data or manual guesswork.
- A shared backtest index shows persistent alpha for strategies selected without purged validation on the same historic tape.
- Generator with SDG axioms disabled matches downstream task pass rate of full SDG generator—axioms add no value (SDG3 retire condition).
- Strategy rules tuned only on synthetic daily data match real 2022-2025 cross-regime performance without degradation.
- Synthetic-only validation approves a rule change that fails the documented 2022 bear cross-regime test on real data.
- Teams with only flat run directories reproduce historic backtests faster than teams with indexed experiment records.

## Source Basis

- `software-testing-framework`
- `software-testing-metrics`
- `software-testing-tools`
- `software-testing-disconfirming`
- `backtest-reproducibility`
- `backtest-walk-forward`
- `hnw-portfolios-sdg-heuristics`
- `daily-synth-validation`
- `synth-fiij-backtest-discipline`
- `backtest-experiment-tracking`

## Next Questions

### Follow-Up — investigate next

1. What observable test, dataset, or experiment would most reduce the uncertainty that aI-generated tests may inflate coverage without meaningful assertions—human review of assertion quality remains necessary, and how far would resolving it move the current credence of 0.89? — This is the run's leading uncertainty driver, so settling it has the highest expected information value.
2. What concrete, pre-resolution indicator would let us monitor the falsifier 'Teams with inverted test pyramid (mostly E2E) show lower production defect escape rate than pyramid-balanced teams at equal CI spend' before 2026-06-29, rather than only learning the answer at resolution? — A falsifier you cannot observe in advance cannot guide updating, so operationalizing it turns the caveat into an actionable check.
3. Does the reference class behind 'Mature software teams organize testing as a pyramid—many fast unit tests, fewer integration tests, and a thin layer of end-to-end tests—because unit tests give the best defect-detection cost ratio while E2E tests catch wiring failures but are slow and flaky' condition on the same regime and scope as the target, and does re-stratifying it shift the prior? — A mis-specified reference class is a common source of miscalibrated base rates.

### What-If — negation probes

1. What if the supporting evidence reverses and 'Testing pyramid and types (unit, integration, E2E, contract, property-based); shift-left and CI integration; test metrics (coverage, branch, mutation score, flake rate, defect escape, MTTR, DORA); toolchain by language and layer (pytest, Jest, Playwright, Testcontainers, k6, SonarQube); disconfirming limits (coverage gaming, flake, ice-cream cone, test-induced design damage); application to quant/research repos with reproducibility and walk-forward validation gates' instead fails before 2026-06-29? — Negating the prevailing lean (credence 0.89); pricing the disconfirming regime as the base case can reveal a hedge or contrarian edge the current view suppresses.
2. What if we treated the routing guardrail — '¬M1 — What if the system is irreducible? (Emergent properties, complexity)' — as the opportunity rather than the thing to avoid? — Heuristic Algebra negation of the active heuristic surfaces paths the default routing suppresses by design.

### Open Sub-Questions — from sources

- Minimum integration test set that catches 90% of cross-module regressions without full staging parity?
- Standard metric card for research/quant repos: which of coverage, mutation score, walk-forward pass, and reproducibility hash should gate merge?
- Minimum toolset for a Python quant monorepo: pytest + hypothesis + coverage gate + reproducible data fixtures—what E2E layer if any?
- When to accept lower coverage on research/experiment branches with mandatory reproducibility artifacts instead of full unit suite?
- Should backtest lineage (extends, supersedes) be first-class catalog edges like research insight cards?
- Should every stored backtest record the full split manifest or only summary metrics and config hashes?
- SDG tension catalog for HNW—standard list of productive contradictions to preserve in base case?
- Which summary statistics must match before a synthetic daily pack is approved for FIIJ methodology testing?
- Should synthetic FIIJ fixtures ship as versioned scenario packs referenced by backtest catalog cards?
- What minimum run card fields are required for a backtest to be referenceable by another researcher?
