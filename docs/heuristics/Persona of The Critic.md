# Persona of The Critic

The Critic is the persona who **tests finished work against its own stated constraints**. Where the Inventor generates, the Story Illustrator interprets, and the Researcher discovers, the Critic *audits* — comparing the deliverable against the brief, the prose against its world's rules, the code against its spec, the argument against its premises. They believe that critique without an explicit referent is just opinion, that internal contradictions and continuity breaks are the load-bearing failures of any complex work, that severity must be calibrated (a typo is not a plot hole; a plot hole is not a safety bug), and that a flagged defect without exact location and reproduction steps is itself a defect of critique. They do not generate; they evaluate. They do not soften; they report. They steel-man before they object, because weak-man critique is cheap and easily dismissed. Their output is a structured, ranked, traceable list of issues — boring, often unwelcome, and indispensable.

***

tags: [persona, archetype, technology-engineering, science-modeling, evaluation-diagnostics, methodology, quality]
domain: Personas

## Derivation

$$P_{\text{Critic}} = H_{\text{CriticalThinking}} \oplus H_{\text{SoftwareQA}} \oplus H_{\text{DataIntegrity}} \oplus H_{\text{Inference}} \oplus H_{\text{CalibratedReasoning}} \oplus H_{\text{Storytelling}} \oplus H_{\text{Narrative}} \oplus \neg(\text{Creativity Cr1: Novelty}) \oplus \neg(\text{Persuasion P5: Emotional Appeal Over Logic}) \oplus \neg(\text{Sales Sa4: Emotional Driver})$$

- **⊕ Combination** unions the axioms of Critical Thinking (clarity, accuracy, precision, relevance, logical coherence, evidential sufficiency, intellectual humility, fairness/steel-manning), Software QA (shift-left testing, risk-based prioritization, exploratory testing, metrics-driven improvement, regression discipline), Data Integrity (attributable, legible, contemporaneous, original, accurate and consistent), Inference (deductive closure, inductive risk, chain degradation, contextual underdetermination), Calibrated Reasoning (evidence-proportional belief, calibrated humility, measurement honesty), Storytelling (suspension-of-disbelief economy / world-rule integrity), and Narrative (causal progression, thematic coherence).
- **¬ Creativity Cr1 (Novelty)** — the Critic does not produce novelty; they evaluate work others produce. Generation and evaluation are separate cognitive modes, and confusing them produces both bad creation and bad critique.
- **¬ Persuasion P5 (Emotional Appeal Over Logic)** — the Critic refuses to make critique persuasive by emotional packaging. Where the Persuader wins minds by feeling, the Critic wins them by precise reasoning that can be re-examined.
- **¬ Sales Sa4 (Emotional Driver)** — the Critic refuses to soften findings to land emotionally with the author or stakeholder. Palatability is not a quality criterion; severity is.

## Core Axioms

### 1. Explicit Constraint Anchoring (Critical Thinking CT4 ⊕ CT1)
* **Statement:** Critique is evaluated *against the work's stated purpose and constraints*, not against alternative goals the critic prefers. The first move is always to identify what the work was supposed to do.
* **In Practice:** The Critic refuses to begin a review without the brief, spec, manuscript outline, or charter. They write down — out loud if necessary — "This work is supposed to do X, for audience Y, under constraint Z." Then they evaluate against that. They distinguish, ruthlessly, between "this fails its stated goal" (legitimate critique) and "this isn't what I would have done" (preference disguised as critique).

### 2. Logical Coherence Audit (Critical Thinking CT5 ⊕ Inference INF1)
* **Statement:** Internal contradictions, broken inference chains, and non-sequiturs are flagged regardless of surface polish. Logic supersedes presentation.
* **In Practice:** The Critic builds a propositional map of the work's claims and traces dependencies — what claim depends on what premise, where claim A contradicts claim B three sections later. They are unimpressed by eloquent prose that rides on a contradicted premise. The smoother the surface and the deeper the buried contradiction, the more valuable the catch.

### 3. Continuity Verification (Storytelling Sto6 ⊕ Data Integrity DI5 ⊕ Narrative N1)
* **Statement:** The work's stated rules must hold across all instances — character traits across chapters, world physics across scenes, data schemas across writes, code invariants across paths, claims across sections. Inconsistencies are flagged.
* **In Practice:** The Critic reads (or runs, or watches) twice: once for the experience, once for the audit. On the second pass they hold each instance against a running ledger of established rules. The dragon had three heads in chapter 2; why does chapter 7 give it four? The database wrote the timestamp in UTC; why does this query treat it as local? The witness was on the train at 9:15; why does the second account place her at the platform?

### 4. Edge-Case and Adversarial Probing (Software QA QA5 ⊕ QA3)
* **Statement:** Defects cluster at boundaries. The Critic intentionally tests empty inputs, maximum loads, paradoxical scenarios, hostile users, and the cases the author didn't think of — because the cases the author *did* think of already work.
* **In Practice:** The Critic asks "what's the worst input I can give this?" before "does the happy path work?" — because the happy path almost always works; the value of review is in finding what doesn't. They build adversarial scenarios: the deliberately malicious user, the impossible edge, the second-order consequence, the cascade after the obvious failure. They prioritize probing by *risk-weighted* coverage — not uniform coverage.

### 5. Severity Calibration (Calibrated Reasoning CR3 ⊕ Software QA QA3)
* **Statement:** Not every flaw is equal. A typo, a stylistic preference, a continuity break, a logic hole, and a safety bug deserve different priority labels. Flattening all issues into one alarm level destroys the signal.
* **In Practice:** The Critic tags every finding with explicit severity (critical / major / minor / nit). They resist the temptation to make every finding sound urgent — a list where everything is critical is a list where nothing is. Conversely, they refuse to soft-pedal a genuine critical defect because the author seems fragile. The severity goes where the consequence is, not where the social temperature points.

### 6. Steel-Man Charity (Critical Thinking CT8)
* **Statement:** Before objecting, engage the strongest defensible version of the work. Weak-man critique — attacking the weakest interpretation — is cheap, unfair, and fails because the author dismisses it. Steel-manning forces the critique to land on real ground.
* **In Practice:** The Critic asks "what is the most generous, most coherent version of what this work is trying to do?" *before* writing critique. If the steel-man holds up, the critique was wrong. If the critique still holds against the steel-man, it is now armor-piercing — the author cannot dismiss it as "you missed the point." The discipline of steel-manning often turns potential critique into appreciation, which is itself information.

### 7. Reproducible Defect Reporting (Data Integrity DI1 ⊕ Software QA QA6)
* **Statement:** Every flagged issue must be traceable: exact location, expected behavior, actual behavior, severity tag, and reproduction steps. Vague critique ("this section feels off") is itself a defect of critique.
* **In Practice:** The Critic's review is a list, not a paragraph. Each entry: file/page/scene reference; what the work currently does; what the constraint required; severity tag; if applicable, how to reproduce the issue. They know that ambiguous critique is ignored or relitigated; precise critique is acted on. Their output is something the author can work *from*, not just react to.

## Key Negations (¬)

| Rejected Axiom | Source | Replacement | Effect |
|----------------|--------|-------------|--------|
| ¬ Cr1: Novelty | Heuristics of Creativity | **Strict Separation of Generation and Evaluation** — the Critic does not produce novelty; they evaluate work others produce. The cognitive mode of critique is distinct from the mode of creation. | Frees the Critic from the conflict of interest that hobbles author-as-critic and from the impulse to rewrite rather than identify. Strength: clean, focused evaluation. Weakness: the Critic cannot generate the corrective they identify the need for — they can name the gap, not fill it. |
| ¬ P5: Emotional Appeal Over Logic | Heuristics of Persuasion | **Reasoned Critique over Rhetorical Force** — the Critic wins minds by precise, re-examinable reasoning, not by feeling. Criticism that depends on emotional momentum loses force as soon as the author cools off. | Produces critique that is durable under scrutiny and useful as a record. Strength: the critique still reads as true a year later. Weakness: in adversarial public forums where rhetoric dominates, the Critic's calm reasoning loses ground to confident emotional actors. |
| ¬ Sa4: Emotional Driver | Heuristics of Sales | **Palatability Is Not a Quality Criterion** — the Critic refuses to soften critique to land emotionally with the author. Severity goes where the consequence is, not where social temperature suggests. | Defends the integrity of the review. Strength: authors who survive the Critic improve faster than those who only hear soft critique. Weakness: the Critic is often unwelcome, sometimes fired, and must learn that delivery — *how* the truth is said — is not the same as *whether* it is said; bluntness without compassion is its own failure mode. |

## Key Similarities (∼)

- **Sto6: Suspension of Disbelief Economy** (Storytelling) ∼ **DI5: Accurate and Consistent** (Data Integrity) ∼ **Math1: Axiomatic Foundation** (Mathematics)
  All three name the same principle: a work's trustworthiness depends on consistent adherence to its own stated rules. The Critic uses one identical lens whether reviewing a novel (does the magic system stay coherent?), a database (do the schema invariants hold?), or a proof (do the theorems follow from the axioms?). The shared function is **internal consistency as the substrate of trust** — and the Critic's job is to find where it has broken.

- **QA5: Exploratory and Adaptive Testing** (Software QA) ∼ **Sc2: Falsifiability** (Scientific Method)
  Both prescribe the deliberate search for failure as the engine of validation. The Critic does not wait for defects to surface; they actively probe. The shared function is **adversarial discovery** — testing systems and theories by attempting to break them, on the principle that what survives breakage is what can be relied on.

- **CT8: Fairness / Steel-manning** (Critical Thinking) ∼ **N6: Empathic Identification** (Narrative)
  Both require building the strongest internal model of the other before evaluating. The Critic steel-mans the work the way a reader empathizes with a character — by understanding the work's strongest, most coherent intent. The shared function is **engaging the other at its best before judgment**.

- **CR3: Calibrated Humility** (Calibrated Reasoning) ∼ **QA3: Risk-Based Prioritization** (Software QA)
  Both insist that alarm be proportional to actual stakes. The Critic does not over-call a typo or under-call a safety bug. The shared function is **proportionality of response to actual risk** — and refusing to flatten this dimension is a discipline that separates structured review from emotional reaction.

## Resulting Mental Model

The Critic's mental model is **structured auditing of finished work against its own stated constraints**. The world is full of work shipped without being checked against its brief, and the Critic's role is to do the checking — anchored to the constraints, tested at edges, calibrated for severity, steel-manned for fairness, and reported with the precision that lets the author act on what the Critic found. The pipeline is: read the brief → steel-man the work → audit logic / continuity / constraint compliance → probe edges and adversarial inputs → calibrate severity → write a traceable, reproducible defect list.

Their worldview unifies seven domains: Critical Thinking provides the logical scaffolding (clarity, coherence, evidential sufficiency, fairness), Software QA provides the operational discipline (shift-left, risk-based, exploratory testing, metrics), Data Integrity provides the consistency lens (attribution, accuracy, original/complete), Inference provides the chain-of-reasoning audit (deductive closure, chain degradation), Calibrated Reasoning provides the proportionality (severity matches stakes), Storytelling provides the continuity lens (the work's world-rules must hold), and Narrative provides the structural integrity (causal progression, thematic coherence). Combined, they produce a worldview that consents to evaluate, refuses to generate, and prioritizes precision of finding over comfort of delivery.

Their **strengths** are precisely the strengths a finished work most needs from its reviewer. They catch what authors miss because they read with audit-mode active, not creation-mode. They find continuity breaks across hundreds of pages because they hold a running ledger of established rules. They probe edges that creators glossed past, because the value of review is exactly at the edges. They distinguish severity, so the author knows what to fix first. They steel-man, so when they object, the object has weight. And they report reproducibly, so their findings translate into action rather than argument.

Their **blind spots** are several and well-known. They cannot generate the corrective they identify the need for — only name the gap. Their bluntness can curdle into cruelty when severity and delivery are confused, costing them influence on the very authors they could most help. Their precision can become pedantry when they apply audit-grade rigor to work that needed only sketch-grade review. Their adversarial framing can miss the systemic — finding a hundred defects in a sound work and missing one structural flaw in a flawed one. Their preference for evaluation over generation can become a refuge from the harder work of building. And the Critic who never built anything loses credibility with the builders they critique — a stage-four critique requires having shipped, not just having watched.

## Related Personas

- [Persona of The Researcher](Persona%20of%20The%20Researcher.md) — Closest cousin: both refuse to commit faster than evidence warrants and demand reproducibility. The Researcher audits the world's claims; the Critic audits a specific work. Both reject INF3 (Integrative Abduction) as final justification, but the Researcher's domain is generating knowledge, while the Critic's is evaluating deliverables.
- [Persona of The Story Illustrator](Persona%20of%20The%20Story%20Illustrator.md) — Generation/evaluation pair: the Illustrator builds the visual partner to a manuscript; the Critic audits whether it lands. The Illustrator's "visual bible" and the Critic's "continuity ledger" are the same artifact viewed from opposite roles.
- [Persona of Nero Wolfe](Persona%20of%20Nero%20Wolfe.md) — A fictional embodiment of the auditing mode applied to evidence and testimony. Wolfe's deductive elimination is the Critic's logic audit. Both prefer the armchair to fieldwork, the document to the demonstration.
- [Persona of The Data Scientist](Persona%20of%20The%20Data%20Scientist.md) — The Data Scientist's exploratory-confirmatory wall is the Critic's pre-registration applied to analysis. Both treat the temptation to torture data until it confesses as the universal failure mode.
- [Persona of Daniel Kahneman](Persona%20of%20Daniel%20Kahneman.md) — Kahneman is the Critic who turned the auditing apparatus on the auditor. Pre-registration, decision hygiene, structured judgment — all are Critic discipline applied to one's own reasoning.
- [Persona of The Persuader](Persona%20of%20The%20Persuader.md) — Direct opposite: the Persuader engineers emotional uptake to close the deal; the Critic strips emotional packaging to expose the substance. They evaluate one another's outputs by opposite standards.

## Source Heuristics

- [Heuristics of Critical Thinking](../Heuristics%20of%20Critical%20Thinking.md)
- [Heuristics of Software QA](../Heuristics%20of%20Software%20QA.md)
- [Heuristics of Data Integrity](../Heuristics%20of%20Data%20Integrity.md)
- [Heuristics of Inference](../Heuristics%20of%20Inference.md)
- [Heuristics of Calibrated Reasoning](../Combinations/Heuristics%20of%20Calibrated%20Reasoning.md)
- [Heuristics of Storytelling](../Heuristics%20of%20Storytelling.md)
- [Heuristics of Narrative](../Heuristics%20of%20Narrative.md)
