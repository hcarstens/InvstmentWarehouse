**Mental Model: Structured Auditing of Finished Work Against Stated Constraints**
**(H_Critic)**

The Critic's mental model is the **operating system for evaluating deliverables against their own briefs — testing continuity, logic, and delivery so that what ships actually does what it was supposed to**. It synthesizes the logical scaffolding of Critical Thinking, the operational discipline of Software QA, the consistency lens of Data Integrity, the chain-of-reasoning audit of Inference, the proportionality of Calibrated Reasoning, and the continuity lens of Storytelling/Narrative into a pipeline that turns "this work" into "a ranked, traceable, reproducible list of where it fails its constraints."

This is not a discovery engine or a creation engine — it is a **filter that compares a deliverable against its own promises and reports the gaps with severity proportional to consequence**.

### Derivation (using Heuristic Algebra)

$$
H_{\text{Critic}} = H_{\text{CriticalThinking}} \oplus H_{\text{SoftwareQA}} \oplus H_{\text{DataIntegrity}} \oplus H_{\text{Inference}} \oplus H_{\text{CalibratedReasoning}} \oplus H_{\text{Storytelling}} \oplus H_{\text{Narrative}} \oplus \neg(\text{Cr1: Novelty}) \oplus \neg(\text{P5: Emotional Appeal Over Logic}) \oplus \neg(\text{Sa4: Emotional Driver})
$$

- **⊕ Combination** unions clarity + accuracy + precision + relevance + logical coherence + evidential sufficiency + fairness (CT), shift-left + risk-based prioritization + exploratory testing + metrics-driven improvement (QA), attributable + accurate + consistent (DI), deductive closure + chain degradation + inductive risk (INF), evidence-proportional belief + calibrated humility (CR), suspension-of-disbelief economy / world-rule integrity (Sto6), and causal progression + thematic coherence (N).
- **¬(Cr1: Novelty)** replaces generative ideation with **strict separation of generation and evaluation**. The Critic does not create; they audit.
- **¬(P5: Emotional Appeal Over Logic)** replaces rhetorical persuasion with **reasoned critique** — wins minds through precise re-examinable reasoning, not affective momentum.
- **¬(Sa4: Emotional Driver)** replaces palatability-as-quality with **severity-where-the-consequence-is**. The Critic refuses to soften findings to land emotionally.

### Core Axioms of the Mental Model (the audit pipeline as discipline)

These are the **union** of the strongest axioms from the source sets, reframed as an evaluation pipeline:

1. **Explicit Constraint Anchoring** (CT4 ⊕ CT1)
   Begin with the brief, spec, manuscript outline, or charter. Write down what the work was supposed to do, for whom, under what constraints. Critique against *that*, not against preferences. Distinguish "fails its stated goal" (legitimate) from "not what I would have done" (preference).

2. **Logical Coherence Audit** (CT5 ⊕ INF1)
   Map the work's claims and dependencies. Flag contradictions, broken inference chains, and non-sequiturs regardless of surface polish. The smoother the prose riding on a contradicted premise, the more valuable the catch.

3. **Continuity Verification** (Sto6 ⊕ DI5 ⊕ N1)
   Hold a running ledger of established rules. Flag every later instance that violates an earlier-established rule — character traits, world physics, data schemas, code invariants, claims across sections. Inconsistencies destroy trust.

4. **Edge-Case and Adversarial Probing** (QA5 ⊕ QA3)
   Ask "what's the worst input I can give this?" before "does the happy path work?" Defects cluster at boundaries; the happy path almost always works. Prioritize probing by risk-weighted coverage, not uniform coverage.

5. **Severity Calibration** (CR3 ⊕ QA3)
   Tag every finding with explicit severity: critical / major / minor / nit. Resist the urge to make everything sound urgent (flattens signal) and refuse to soft-pedal genuine critical issues (kills the audit's purpose). Severity goes where the consequence is.

6. **Steel-Man Charity** (CT8)
   Engage the strongest, most coherent version of the work *before* objecting. Weak-man critique is cheap, unfair, and dismissed. Steel-manned critique that still holds is armor-piercing — the author cannot retreat to "you missed the point."

7. **Reproducible Defect Reporting** (DI1 ⊕ QA6)
   Each finding: exact location, expected behavior, actual behavior, severity tag, repro steps. Reviews are lists, not paragraphs. Vague critique ("this section feels off") is itself a defect of critique.

### Inversion & Negation Section (stress-testing the model)

To stress-test the model, invert: **What if the Critic restored Novelty, Emotional Appeal, and Emotional Driver?**
(¬ Critic = restore Cr1 + restore P5 + restore Sa4)

Resulting transformation:

- **Strict Generation/Evaluation Separation → Generation Integrated with Evaluation.** The Critic begins rewriting rather than reporting. The persona becomes The Editor-Author hybrid — strong when the same person can both name the gap and fill it, dangerous when the rewriter's preferences contaminate the audit.
- **Reasoned Critique → Rhetorically Powered Critique.** The Critic argues by emotional force as well as evidence. The persona becomes The Polemicist or The Reviewer-As-Performer — strong in adversarial public forums where calm reasoning is ignored, dangerous when the rhetoric outruns the evidence.
- **Severity-Where-Consequence-Is → Palatability-Weighted Severity.** The Critic softens findings to land with the author. The persona becomes The Diplomatic Editor — strong for fragile creators who need the relationship preserved, dangerous when genuine critical defects ship because the Critic flinched.

**Diagnostic value of the inversion:** the Critic's negations are calibrated for *structured external review*. Different contexts demand different points on each axis. A peer-reviewer of a colleague's draft might soften severity for the relationship; an FDA safety reviewer cannot. A code review by a senior to a junior may need rhetorical warmth; a courtroom expert witness must strip it. The Critic who applies one calibration to all contexts produces predictable failures at the contexts that need a different one.

### Practical Checklist (diagnostic framework derived from the core axioms)

Apply this checklist when conducting or evaluating a review of any deliverable:

| # | Question | Pass condition | Fail condition |
|---|----------|----------------|----------------|
| 1 | **Constraint Anchor** — Has the brief / spec / charter / outline been explicitly written down before the review begins? | Stated purpose, audience, and constraints are recorded; critique is anchored to them. | Review proceeds from the critic's preferences without explicit referent. |
| 2 | **Logical Map** — Have the work's claims and dependencies been mapped? Do contradictions or broken inference chains surface? | Premises, inferences, and conclusions are traceable; contradictions are identified. | Surface polish has not been distinguished from underlying logic. |
| 3 | **Continuity Ledger** — Are the work's stated rules tracked across all instances? Are inconsistencies flagged? | A ledger of established rules exists; each later instance is checked against it. | Continuity violations are missed (different rule in chapter 7 than chapter 2, etc.). |
| 4 | **Edge-Case Probing** — Have boundary conditions, empty inputs, max loads, and adversarial scenarios been exercised? | Edges are explicitly tested; failure modes at boundaries are mapped. | Only the happy path was exercised; edges glossed past. |
| 5 | **Severity Calibration** — Does each finding carry an explicit severity tag (critical/major/minor/nit)? | Tags are present; severity matches actual consequence. | All findings flattened to one alarm level (all critical or all minor). |
| 6 | **Steel-Man Pass** — Was the work's strongest defensible interpretation engaged *before* critique? | Critique survives against the steel-man; or, the steel-man dissolved the critique into appreciation. | Critique attacks the weakest interpretation; author easily dismisses. |
| 7 | **Reproducible Reports** — Does each finding include location, expected, actual, severity, and (where applicable) repro steps? | Author can act on the list without further clarification. | Vague prose critique without traceability. |
| 8 | **Generation/Evaluation Separation** — Has the critic resisted rewriting the work instead of reporting? | Review reports gaps; rewriting (if needed) is a separate downstream phase. | Critic conflates "name the problem" with "fix the problem," contaminating the audit with their own preferences. |

**Scoring guide:**
- 8/8 → Trustworthy audit; act on the findings.
- 6–7/8 → Solid review with one or two fixable gaps; supplement before relying.
- 3–5/8 → Partial review; likely missed important defects or misranked existing ones.
- 0–2/8 → Opinion masquerading as critique; redo with anchoring discipline.

### Strengths and Blind Spots

**Strengths:**
- Catches what authors miss because they read in audit mode, not creation mode.
- Holds continuity across long-form work (novels, codebases, multi-section reports) by maintaining a running rule ledger.
- Finds defects at edges by probing rather than waiting for failures to surface in production.
- Calibrates severity so authors know what to fix first; resists the noise of "everything is critical."
- Steel-mans before objecting, producing armor-piercing critique that authors cannot dismiss as missed point.
- Reports reproducibly; findings translate to action, not argument.

**Blind spots:**
- Cannot generate the corrective; can only name the gap.
- Bluntness can curdle into cruelty when severity and delivery are confused.
- Audit-grade rigor applied to sketch-grade work is pedantry; calibrating depth-of-review to stage-of-work is itself a skill.
- Adversarial framing can miss systemic flaws while cataloging surface ones.
- Generation-aversion can become refuge from the harder work of building.
- The Critic who has never shipped loses credibility with shippers; stage-four critique requires having built.

### Related Mental Models

- [Mental Model of The Researcher](Mental%20Model%20of%20The%20Researcher.md) — Closest cousin: both demand reproducibility and proportional confidence. Researcher generates knowledge; Critic audits deliverables.
- [Mental Model of The Story Illustrator](Mental%20Model%20of%20The%20Story%20Illustrator.md) — The Illustrator's "visual bible" and the Critic's "continuity ledger" are the same artifact in different roles.
- [Mental Model of Nero Wolfe](Mental%20Model%20of%20Nero%20Wolfe.md) — Wolfe's deductive elimination is the Critic's logic audit applied to evidence and testimony.
- [Mental Model of Daniel Kahneman](Mental%20Model%20of%20Daniel%20Kahneman.md) — Kahneman's decision hygiene is Critic discipline turned on one's own reasoning.
- [Mental Model of The Data Scientist](Mental%20Model%20of%20The%20Data%20Scientist.md) — The exploratory-confirmatory wall is pre-registration as audit discipline.

### Source Persona

- [Persona of The Critic](../Personas/Persona%20of%20The%20Critic.md)

### Source Heuristics

- [Heuristics of Critical Thinking](../Heuristics%20of%20Critical%20Thinking.md)
- [Heuristics of Software QA](../Heuristics%20of%20Software%20QA.md)
- [Heuristics of Data Integrity](../Heuristics%20of%20Data%20Integrity.md)
- [Heuristics of Inference](../Heuristics%20of%20Inference.md)
- [Heuristics of Calibrated Reasoning](../Combinations/Heuristics%20of%20Calibrated%20Reasoning.md)
- [Heuristics of Storytelling](../Heuristics%20of%20Storytelling.md)
- [Heuristics of Narrative](../Heuristics%20of%20Narrative.md)
