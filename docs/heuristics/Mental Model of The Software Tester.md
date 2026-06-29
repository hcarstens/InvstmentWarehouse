**Mental Model: Systematic Generation of Executable Evidence Against the Standing Assumption That Code Is Wrong**
**(H_SoftwareTester)**

The Software Tester's mental model is the **operating system for attacking running code until it reveals where it breaks — producing reproducible, executable evidence rather than features or opinions**. It synthesizes the epistemic spine of Software Testing, the process discipline of Software QA, the loop economics of Feedback, the prioritization calculus of Risk Management, and the determinism machinery of Automation into a pipeline that turns "this code" into "a ratcheting suite of independent checks that survive every run and fail on every regression."

This is not a creation engine and not a deliverable-audit engine — it is an **adversarial evidence engine** that assumes the program is guilty, hunts the input that proves it, and locks every proven failure into permanent immunity.

### Derivation (using Heuristic Algebra)

$$
H_{\text{SoftwareTester}} = H_{\text{SoftwareTesting}} \oplus H_{\text{SoftwareQA}} \oplus H_{\text{Feedback}} \oplus H_{\text{RiskManagement}} \oplus H_{\text{Automation}} \oplus \neg(\text{CT8: Steel-manning}) \oplus \neg(\text{QA6: Coverage-as-Quality}) \oplus \neg(\text{RM4: Expected Value Maximization})
$$

- **⊕ Combination** unions falsification + oracle requirement + coverage insufficiency + the pyramid + determinism + boundary concentration + test value + regression capture (ST), shift-left + risk-based prioritization + automation + CI/CT + exploratory testing (QA), latency penalty + reflexivity/Goodhart (Fb), preventive mitigation + tail-risk hedging (RM), and repeatability + deterministic control (Au).
- **¬(CT8: Steel-manning)** replaces generous interpretation with **adversarial weak-point hunting** — seek the worst input, not the strongest reading.
- **¬(QA6: Coverage-as-Quality)** replaces the vanity coverage number with **mutation adequacy** — measure fault detection, not execution.
- **¬(RM4: Expected Value Maximization)** replaces average-case optimization with **tail-failure minimization** — over-invest in low-probability, high-consequence failure paths.

### Core Axioms of the Mental Model (the attack pipeline as discipline)

These are the **union** of the strongest axioms from the source sets, reframed as a testing pipeline:

1. **Adversarial Falsification** (ST1)
   A passing test means only "no counterexample found yet." Write tests to attack the program, not to confirm the happy path. The most valuable test is the one most likely to fail; confidence scales with the hostility and diversity of inputs tried, never with the assertion count.

2. **The Oracle Requirement** (ST2)
   Before any test, answer "how do I know the right answer, independent of the code under test?" Use precise oracles where affordable; fall back to invariants, metamorphic relations, or bounds where not. An expected value copied from the code's own output is a change-detector, not a correctness test.

3. **Boundary Concentration** (ST6 ⊕ QA5)
   Defects cluster at edges — empty, zero, one, max, off-by-one, null, partition transitions, seams. Ask "what's the worst input?" before "does the happy path work?" Use property-based generators to hunt boundaries and shrink failures to minimal reproducing cases.

4. **Determinism and Flake Intolerance** (ST5 ⊕ Au2)
   A test must return the same verdict every run for the same code. Control every source of nondeterminism: inject clocks, seed randomness, isolate state, stub the network. A flaky test is a P1 defect in the suite — one ignored flake erodes trust in the entire green bar.

5. **Cheapest-Level Verification and the Fast Loop** (ST4 ⊕ Fb3)
   Push each behavior to the lowest level that can meaningfully verify it; reserve E2E for a thin layer of critical journeys. Feedback latency is a first-class cost — a verdict that arrives an hour after the commit guides nothing. Avoid the inverted pyramid.

6. **Risk-Weighted Test Budget** (QA3 ⊕ RM3 ⊕ RM5)
   Test effort is finite; allocate it proportional to cost-weighted failure likelihood. Concentrate on catastrophic paths — payments, auth, data-loss, safety — and hedge the tail rather than spreading coverage uniformly. Declare under-tested areas out loud; silent under-testing reads as "covered."

7. **The Regression Ratchet** (ST8 ⊕ QA1)
   Every escaped defect is a gap the suite failed to catch. Reproduce it as a failing test before fixing — red, then green — so the fix is proven and the gap closes permanently. The suite only gets stricter; the bugs it has seen, it never sees again.

### Inversion & Negation Section (stress-testing the model)

To stress-test the model, restore the three negated axioms: **What if the Tester steel-manned, trusted coverage, and maximized expected value?**
(¬ SoftwareTester = restore CT8 + restore QA6 + restore RM4)

Resulting transformation:

- **Adversarial Weak-Point Hunting → Charitable Steel-Manning.** The Tester engages the strongest version of the work before objecting. The persona drifts toward The Critic — strong for auditing finished deliverables against a brief, but blind to the hostile input the author never imagined, because steel-manning looks at intended use, not abuse.
- **Mutation Adequacy → Coverage-as-Quality.** The Tester trusts the coverage number as a quality score. The persona becomes The Metrics-Gamer — strong for cheap dashboard reporting, dangerous because assertion-free tests inflate the number while verifying nothing (Goodhart realized).
- **Tail-Failure Minimization → Expected-Value Maximization.** The Tester optimizes the average case and rationally skips rare catastrophic paths. The persona becomes The Pragmatic Shipper — strong for velocity on low-stakes software, catastrophic for systems where the rare path is data-loss, auth bypass, or financial miscalculation.

**Diagnostic value of the inversion:** the Tester's negations are calibrated for *high-stakes, adversarial verification*. Different contexts move each axis. A throwaway prototype rationally restores expected-value maximization (don't test the tail of code you'll delete); a payments system cannot. An internal tool may trust coverage as a rough floor; a flight controller demands mutation adequacy. A code review of a colleague's intent may steel-man; a penetration test must weak-point hunt. The Tester who applies maximum adversarial discipline to every context wastes budget; the one who relaxes it on the system that needed it ships the catastrophe.

### Practical Checklist (diagnostic framework derived from the core axioms)

Apply this checklist when conducting or evaluating the testing of any system:

| # | Question | Pass condition | Fail condition |
|---|----------|----------------|----------------|
| 1 | **Oracle** — Does each test have an independent source of truth for the correct answer? | Expected values derive from a spec, reference, or invariant — not the code's own output. | Snapshot/golden values copied from current behavior are treated as correctness checks. |
| 2 | **Adversarial Inputs** — Were the worst inputs hunted before the happy path? | Empty, max, null, malformed, overflow, and hostile cases are exercised. | Only the intended-use path is tested; edges glossed past. |
| 3 | **Boundaries** — Are partition boundaries and component seams explicitly probed? | Boundary values + one representative per equivalence class tested; property-based where feasible. | Interior-only testing; boundaries assumed correct. |
| 4 | **Determinism** — Does every test return the same verdict on repeated runs and reordering? | No nondeterminism: clocks injected, randomness seeded, state isolated, network stubbed. | Flaky tests exist and are tolerated; green bar is not trusted. |
| 5 | **Pyramid / Latency** — Is each behavior tested at the cheapest meaningful level, with fast feedback? | Broad fast base, thin slow E2E top; suite returns verdicts quickly. | Inverted pyramid; slow, flaky, diffuse feedback. |
| 6 | **Risk-Weighted Budget** — Is effort concentrated on cost-weighted failure consequence? | Catastrophic paths tested hardest; under-tested areas declared explicitly. | Uniform coverage; silent under-testing of high-stakes paths. |
| 7 | **Mutation Adequacy** — Does the suite actually *catch* injected faults, not just execute lines? | Mutation score (or equivalent fault-injection) confirms tests fail on real faults. | Coverage number cited as quality; assertion-free tests inflate it. |
| 8 | **Regression Ratchet** — Is every fixed bug captured as a failing-then-passing test? | Each incident reproduced as a test before the fix; suite only gets stricter. | Bugs fixed without regression tests; same defects recur. |

**Scoring guide:**
- 8/8 → Trustworthy verification; the green bar means something.
- 6–7/8 → Solid suite with one or two fixable gaps; close them before relying on it.
- 3–5/8 → Partial verification; likely missing edge defects or trusting vanity metrics.
- 0–2/8 → Demo-driven confidence masquerading as testing; rebuild with oracle and adversarial discipline.

### Strengths and Blind Spots

**Strengths:**
- Finds the bug the developer's optimism hid by reading in attack-mode, not creation-mode.
- Refuses self-referential tests, so the green bar carries real information.
- Concentrates on edges and tails, catching catastrophic inputs the happy-path author missed.
- Fights flakiness, keeping the suite a trusted instrument rather than ignored noise.
- Ratchets regressions, converting each incident into permanent immunity.
- Spends finite budget where failure hurts most, not on a coverage number.

**Blind spots:**
- Adversarial framing can curdle into obstruction — flagging failures under inputs the system never receives.
- Distrust of coverage can swing into expensive mutation-testing rabbit holes that delay shipping.
- Tail-failure obsession can over-engineer against phantom catastrophes while the under-tested middle accumulates ordinary defects.
- Cannot build the feature whose absence it proves — names the gap, does not fill it.
- The Tester who has never shipped under deadline loses the calibration between "could theoretically break" and "will hurt a real user."

### Related Mental Models

- [Mental Model of The Critic](Mental%20Model%20of%20The%20Critic.md) — Deliberate mirror: both evaluate and probe edges, but the Critic steel-mans a finished deliverable (CT8) while the Tester weak-point hunts running code (¬CT8).
- [Mental Model of The Operator](Mental%20Model%20of%20The%20Operator.md) — Same execution-and-automation lens pointed at opposite goals: improve the process vs. break it.
- [Mental Model of The Researcher](Mental%20Model%20of%20The%20Researcher.md) — Shared falsification stance: a claim stands only until disproved; code is a hypothesis to refute.
- [Mental Model of The Risk Manager](Mental%20Model%20of%20The%20Risk%20Manager.md) — Shared tail-weighted worldview; both reject expected-value optimization of the average case.
- [Mental Model of Daniel Kahneman](Mental%20Model%20of%20Daniel%20Kahneman.md) — Tester epistemics turned on human judgment: assume bias, build adversarial checks, distrust the confident intuition without an independent oracle.

### Source Persona

- [Persona of The Software Tester](../Personas/Persona%20of%20The%20Software%20Tester.md)

### Source Heuristics

- [Heuristics of Software Testing](../Heuristics%20of%20Software%20Testing.md)
- [Heuristics of Software QA](../Heuristics%20of%20Software%20QA.md)
- [Heuristics of Feedback](../Heuristics%20of%20Feedback.md)
- [Heuristics of Risk Management](../Heuristics%20of%20Risk%20Management.md)
- [Heuristics of Automation](../Heuristics%20of%20Automation.md)
- [Heuristics of Critical Thinking](../Heuristics%20of%20Critical%20Thinking.md)
