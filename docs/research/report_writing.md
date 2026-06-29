# Research report writing — formats, tools, and document structure

Run status: `complete`

Research quality score: `10/10`

## Bottom Line

Synthesis for 'Research report writing — formats, tools, and document structure': 92 supporting claim(s), 27 disconfirming claim(s); deterministic credence 0.892. 10 open sub-question(s) recorded.

## Base Rates

- Effective research reports follow a reader-first structure: front matter (title, date, audience, classification) → executive summary or abstract → context/problem statement → methods or evidence basis → findings organized by theme not chronology → implications/recommendations → limitations and falsifiers → appendices for supporting data—readers who need decisions read the first two pages; specialists drill into body and appendices.
- Research reports flow through a source format (usually Markdown or Word for drafting) → structured intermediate (JSON terrain map, YAML front matter) → rendered deliverables (PDF, HTML, DOCX)—teams that pick format by audience and lifecycle stage avoid rework; teams that pick one format for all stages pay conversion tax or lose traceability.
- Modern report production stacks combine (1) authoring environment, (2) reference/citation manager, (3) figure/table pipeline, (4) template engine, (5) review workflow, (6) publication channel—research-agent pipelines add (7) structured evidence extraction and (8) terrain-map scoring as pre-publish gates.
- Financial reports split into regulatory filings (standardized sections, XBRL, audit), sell-side research (thesis, valuation, risks), buy-side and family office (IPS memos, performance attribution, risk packs, tax summaries), and internal research (terrain maps, scenario briefs)—each genre has mandatory sections, audience-specific tone, and liability surface that general report frameworks must adapt to.
- Report writing programs fail when structure substitutes for evidence (template compliance without traceability), executive summaries cherry-pick findings, identical templates hide incompatible units or time periods, revision churn erodes version control, or polished prose outruns data vintage—readers gain confidence without justified belief.
- Investment workflows at tech-enabled family offices decompose into data plane (ingest, master data, ledger), research plane (signals, scenarios, backtests), decision plane (IPS, optimization, approvals), execution plane (OMS, routing, settlement), and reporting plane (performance, risk, tax)—each with distinct SLAs and failure modes.
- Managing a family office portfolio decomposes into ten consideration clusters—(1) governance & IPS, (2) entity & household structure, (3) data & reconciliation, (4) strategic allocation & rebalancing, (5) after-tax optimization, (6) liquidity & cash flow, (7) alternatives & illiquids, (8) research & scenarios, (9) execution & operations, (10) reporting & audit—with failure concentrated in (3) and (6) not optimizer sophistication.
- Prioritized consideration checklist for managing a family office portfolio (build + operate): Tier 1 must be correct before Tier 2 matters—data/reconciliation, IPS/governance, liquidity; Tier 2 after-tax optimization and rebalance; Tier 3 research/scenarios; Tier 4 execution automation; Tier 5 exotic tax and alts structuring.
- InvestmentWarehouse is a tech-enabled multi-family office platform shell implementing Sharpe brief priorities—after-tax north star, five operational planes, six workflows—dashboard-first with `warehouse serve` as living status report.
- Dollar-denominated tail units translate distribution to P&L: VaR_α,h = quantile of loss distribution at confidence α over horizon h; ES (CVaR) = expected loss given loss exceeds VaR—ES is coherent risk measure, VaR is not subadditive but widely reported.

## Uncertainty Drivers

- LLM-assisted drafting may inflate fluency without improving structure—human outline and section checklist still gate quality.
- DOCX-from-Markdown via Pandoc may lose complex table formatting—financial tables often need manual polish or LaTeX intermediate.
- AI writing assistants (Copilot, Claude, Cursor) accelerate first drafts but may homogenize voice and skip limitation sections—editorial checklist remains necessary.
- AI-generated sell-side summaries may accelerate draft but increase hallucinated financial figures—human sign-off on all numbers remains mandatory.
- Whether automated report scoring (completeness rubrics) correlates with decision quality or merely checklist compliance.
- Sharpe may prioritize simulation and planning over live trading in first six months given "optimization" and "wealth data model" emphasis in company overview.
- Build-vs-buy (native ledger vs Addepar/Orion) shifts which considerations are in-house vs vendor.
- Income-without-principal-drawdown objective not fully modeled in optimizer v0—open product question.
- Heuristic agents and report writer integration with dashboard and approval gates—in TODO open questions.
- Which α family offices use vs banks (95% vs 99.5%)—unit not comparable across shops without metadata.

## Falsifiers

- BLUF-structured reports with traceable claims show no faster stakeholder decisions than narrative-chronology reports at equal evidence quality.
- Markdown-source CI-rendered PDFs show higher exhibit error rate than Word-native financial reports at equal review headcount.
- DHA terrain-map quality rubric (traceability, falsifiers, uncertainty) fails to predict lower client complaint rate than unstructured memos.
- Mandatory IMRAD structure improves comprehension for 3-page IPS memos vs compressed policy-brief format.
- LLM-drafted reports with source grounding match human-only reports on stale-exhibit incidence in quarterly performance packs.
- Reports with BLUF + traceable claims show higher stakeholder decision speed than narrative-chronology reports at equal word count and evidence quality.
- Teams using Markdown-source + automated PDF render show higher exhibit error rate than Word-native teams at equal review headcount.
- Teams with Pandoc/Quarto CI render show more stale-exhibit incidents than teams with manual Word refresh at equal report frequency.
- Clients receiving BLUF performance letters with linked quantitative appendix show higher retention than narrative-only letters without exhibit traceability.
- Reports passing DHA-style quality rubric (traceability, falsifiers, uncertainty) show no lower client complaint rate than unstructured memos at equal portfolio outcomes.
- Investment workflows that skip reconciliation and operate on custodian API snapshots without lot ledger support tax-aware recommendations at scale.
- Median greenfield family office platform reaches advisor trust without lot-level reconciliation in first 12 months.
- Platform with Tier 2 optimizer but Tier 1 reconciliation breaks shows higher advisor NPS than reversed priority.
- Dashboard panels show stub data while backend claims live reconciliation—violates dashboard-first rule.
- 252-day historical 95% 1d VaR breaches more than 8% of days on 60/40 walk-forward 2010–2025.

## Source Basis

- `report-writing-framework`
- `report-writing-formats`
- `report-writing-tools`
- `financial-report-writing`
- `report-writing-disconfirming`
- `sharpe-investment-workflows-systems`
- `family-office-portfolio-framework`
- `family-office-considerations-checklist`
- `investmentwarehouse-platform-context`
- `dollar-tail-risk-units`

## Next Questions

### Follow-Up — investigate next

1. What observable test, dataset, or experiment would most reduce the uncertainty that lLM-assisted drafting may inflate fluency without improving structure—human outline and section checklist still gate quality, and how far would resolving it move the current credence of 0.89? — This is the run's leading uncertainty driver, so settling it has the highest expected information value.
2. What concrete, pre-resolution indicator would let us monitor the falsifier 'BLUF-structured reports with traceable claims show no faster stakeholder decisions than narrative-chronology reports at equal evidence quality' before 2026-06-29, rather than only learning the answer at resolution? — A falsifier you cannot observe in advance cannot guide updating, so operationalizing it turns the caveat into an actionable check.
3. Does the reference class behind 'Effective research reports follow a reader-first structure: front matter (title, date, audience, classification) → executive summary or abstract → context/problem statement → methods or evidence basis → findings organized by theme not chronology → implications/recommendations → limitations and falsifiers → appendices for supporting data—readers who need decisions read the first two pages; specialists drill into body and appendices' condition on the same regime and scope as the target, and does re-stratifying it shift the prior? — A mis-specified reference class is a common source of miscalibrated base rates.

### What-If — negation probes

1. What if the supporting evidence reverses and 'General and financial research report writing: document structure (IMRAD, BLUF, pyramid principle, section taxonomy), output formats (Markdown, PDF, DOCX, LaTeX, HTML, JSON terrain maps), authoring and publishing tools (Word, Quarto, Pandoc, LaTeX, research-agent pipelines), financial report genres (IPS memos, performance/risk packs, sell-side notes, regulatory filings), traceability and quality gates, and disconfirming limits (template cargo cult, stale exhibits, false precision); application to DHA terrain-map outputs and InvestmentWarehouse heuristic report writer' instead fails before 2026-06-29? — Negating the prevailing lean (credence 0.89); pricing the disconfirming regime as the base case can reveal a hedge or contrarian edge the current view suppresses.
2. What if we treated the routing guardrail — '¬M1 — What if the system is irreducible? (Emergent properties, complexity)' — as the opportunity rather than the thing to avoid? — Heuristic Algebra negation of the active heuristic surfaces paths the default routing suppresses by design.

### Open Sub-Questions — from sources

- Minimum section set for DHA terrain-map outputs consumed by domain writer and client portal—terrain_map.md alone vs mandated executive summary layer?
- Standard DHA output bundle: terrain_map.md + domain_writer/summary.md + PDF one-pager— which format is client-of-record?
- Minimum tool chain for InvestmentWarehouse heuristic report writer: terrain_map.json → Quarto template → PDF + approval gate?
- Standard report bundle for InvestmentWarehouse Tier 3 heuristic report writer: IPS drift + tax what-if + scenario summary + frozen terrain_map.json?
- When to ship terrain_map.md only vs require human-edited executive summary before client delivery?
- Which workflows are in-scope for v1 pilot—full rebalance or tax-loss harvest opportunistic only?
- Unified consideration scorecard per household with friction-weighted priority queue?
- Publish machine-readable consideration manifest per household in warehouse dashboard API?
- Sync family-office consideration manifest to InvestmentWarehouse docs/research/ after each DHA run?
- Report VaR and ES side-by-side with explicit (α, h) in InvestmentWarehouse risk panel?
