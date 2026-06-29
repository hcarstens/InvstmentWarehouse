# What types of reports does a wealth manager write?

Run status: `complete`

Research quality score: `10/10`

## Bottom Line

Synthesis for 'What types of reports does a wealth manager write?': 76 supporting claim(s), 22 disconfirming claim(s); deterministic credence 0.892. 9 open sub-question(s) recorded.

## Base Rates

- A wealth manager produces reports along three axes—(1) audience (client, household principal, investment committee, compliance, regulators, CPAs/estate counsel), (2) cadence (onboarding, quarterly, annual, event-driven, ad hoc), (3) function (policy, performance, risk, tax, planning, research, operations)—most firms ship 12–20 distinct report types across the client lifecycle even when branded under fewer template names.
- Client-facing wealth management reports prioritize clarity, as-of dating, and benchmark transparency over analytical density—successful packs separate narrative (what happened and why) from exhibits (numbers that must reconcile to custodian statements) and never mix unaudited projections with realized performance without labeling.
- Internal wealth management reports enable investment decisions, compliance defense, and operational control—they are often more structured than client-facing documents (explicit thesis, position sizing, kill criteria, audit trail) and feed CRM, OMS, and document management systems before any client-safe derivative is generated.
- Wealth management reporting programs fail when volume substitutes for relevance (clients ignore 40-page quarterly packs), templates desynchronize across authors (letter says one thing, performance PDF another), unaudited projections appear adjacent to realized returns, tax summaries lag custodian 1099s, or polished macro letters disconnected from actual trades—structure and branding increase confidence without improving justified belief.
- Family office execution plane stages trades after advisor approval—OMS routes or records fills; post-trade reconciliation closes loop to lot ledger; reporting plane delivers performance, risk, and tax reporting to family, CPAs, and external counsel.
- Managing a family office portfolio decomposes into ten consideration clusters—(1) governance & IPS, (2) entity & household structure, (3) data & reconciliation, (4) strategic allocation & rebalancing, (5) after-tax optimization, (6) liquidity & cash flow, (7) alternatives & illiquids, (8) research & scenarios, (9) execution & operations, (10) reporting & audit—with failure concentrated in (3) and (6) not optimizer sophistication.
- Prioritized consideration checklist for managing a family office portfolio (build + operate): Tier 1 must be correct before Tier 2 matters—data/reconciliation, IPS/governance, liquidity; Tier 2 after-tax optimization and rebalance; Tier 3 research/scenarios; Tier 4 execution automation; Tier 5 exotic tax and alts structuring.
- Report writing programs fail when structure substitutes for evidence (template compliance without traceability), executive summaries cherry-pick findings, identical templates hide incompatible units or time periods, revision churn erodes version control, or polished prose outruns data vintage—readers gain confidence without justified belief.
- InvestmentWarehouse is a tech-enabled multi-family office platform shell implementing Sharpe brief priorities—after-tax north star, five operational planes, six workflows—dashboard-first with `warehouse serve` as living status report.

## Uncertainty Drivers

- Digital portal dashboards may replace static PDFs for some report types while regulatory and CPA handoffs still require frozen PDF or XBRL exports.
- Client preference for short video summary vs PDF letter varies by generation and AUM tier—delivery channel not yet standardized industry-wide.
- AI-assisted draft IC memos may accelerate workflow but require human attestation on all figures and forward-looking statements.
- Whether digital interactive dashboards reduce complaint rates vs PDF-only delivery when underlying data quality is held constant.
- Trade surveillance and regulatory reporting depth for RIA-wrapped family office.
- Build-vs-buy (native ledger vs Addepar/Orion) shifts which considerations are in-house vs vendor.
- Income-without-principal-drawdown objective not fully modeled in optimizer v0—open product question.
- Whether automated report scoring (completeness rubrics) correlates with decision quality or merely checklist compliance.
- Heuristic agents and report writer integration with dashboard and approval gates—in TODO open questions.

## Falsifiers

- Unified quarterly portal with linked exhibits shows no fewer client number-mismatch complaints than separate letter, performance, and tax PDFs.
- BLUF client letters with exhibit cross-reference ids show no higher meeting-to-action conversion than narrative-only letters.
- RIAs with trade rationale → IPS check → client exhibit chain show same examination deficiency rate as disconnected Word/Excel workflows.
- Minimum report bundle of IPS drift + performance + tax + alts calendar shows no better advisor efficiency than comprehensive 30-page quarterly pack.
- Wealth managers delivering 12+ distinct report types show higher client retention than firms consolidating to 4 templated artifacts at equal AUM.
- Firms delivering unified quarterly portal with linked exhibits show lower client-reported "number mismatch" complaints than firms shipping separate letter, performance, and tax PDFs without cross-reference ids.
- Clients receiving BLUF-structured quarterly letter with exhibit cross-reference ids show higher meeting-to-action conversion than narrative-only letters without linked performance appendix.
- RIAs with linked trade rationale → IPS check → client letter exhibit chain show lower deficiency findings in examination than firms with disconnected Word and Excel workflows.
- Wealth managers shipping unified report bundle with frozen snapshot id show no reduction in client "numbers don't match" complaints vs legacy multi-PDF workflow at equal reconciliation quality.
- Staged-order workflow without post-trade recon shows no increase in lot ledger accuracy vs manual entry.
- Median greenfield family office platform reaches advisor trust without lot-level reconciliation in first 12 months.
- Platform with Tier 2 optimizer but Tier 1 reconciliation breaks shows higher advisor NPS than reversed priority.
- Reports passing DHA-style quality rubric (traceability, falsifiers, uncertainty) show no lower client complaint rate than unstructured memos at equal portfolio outcomes.
- Dashboard panels show stub data while backend claims live reconciliation—violates dashboard-first rule.

## Source Basis

- `wealth-manager-reports-framework`
- `wealth-manager-reports-client-facing`
- `wealth-manager-reports-internal`
- `wealth-manager-reports-disconfirming`
- `family-office-execution-reporting`
- `family-office-portfolio-framework`
- `family-office-considerations-checklist`
- `report-writing-disconfirming`
- `investmentwarehouse-platform-context`

## Next Questions

### Follow-Up — investigate next

1. What observable test, dataset, or experiment would most reduce the uncertainty that digital portal dashboards may replace static PDFs for some report types while regulatory and CPA handoffs still require frozen PDF or XBRL exports, and how far would resolving it move the current credence of 0.89? — This is the run's leading uncertainty driver, so settling it has the highest expected information value.
2. What concrete, pre-resolution indicator would let us monitor the falsifier 'Unified quarterly portal with linked exhibits shows no fewer client number-mismatch complaints than separate letter, performance, and tax PDFs' before 2026-06-29, rather than only learning the answer at resolution? — A falsifier you cannot observe in advance cannot guide updating, so operationalizing it turns the caveat into an actionable check.
3. Does the reference class behind 'A wealth manager produces reports along three axes—(1) audience (client, household principal, investment committee, compliance, regulators, CPAs/estate counsel), (2) cadence (onboarding, quarterly, annual, event-driven, ad hoc), (3) function (policy, performance, risk, tax, planning, research, operations)—most firms ship 12–20 distinct report types across the client lifecycle even when branded under fewer template names' condition on the same regime and scope as the target, and does re-stratifying it shift the prior? — A mis-specified reference class is a common source of miscalibrated base rates.

### What-If — negation probes

1. What if the supporting evidence reverses and 'Taxonomy of wealth management report types by audience (client, IC, compliance, external counsel), cadence (onboarding, quarterly, annual, event-driven), and function (policy, performance, risk, tax, planning, research, operations); mandatory elements and genre structure for client-facing vs internal reports; wirehouse vs RIA vs MFO differences; disconfirming limits (overload, template desync, false precision); mapping to InvestmentWarehouse reporting plane and heuristic report writer' instead fails before 2026-06-29? — Negating the prevailing lean (credence 0.89); pricing the disconfirming regime as the base case can reveal a hedge or contrarian edge the current view suppresses.
2. What if we treated the routing guardrail — '¬M1 — What if the system is irreducible? (Emergent properties, complexity)' — as the opportunity rather than the thing to avoid? — Heuristic Algebra negation of the active heuristic surfaces paths the default routing suppresses by design.

### Open Sub-Questions — from sources

- Minimum report bundle for UHNW household: IPS drift + performance + tax + alts K-1 calendar + scenario one-pager?
- Standard client portal tile set: performance, drift, tax YTD, liquidity runway, alts calendar—each frozen PDF on demand?
- Minimum internal report set for InvestmentWarehouse advisor dashboard: drift + trade list + tax delta + scenario terrain per household?
- When does report count become liability—minimum viable quarterly touch for $10M vs $100M household?
- Security layer (auth, RLS, request logging) gating for external UHNW pilot?
- Unified consideration scorecard per household with friction-weighted priority queue?
- Publish machine-readable consideration manifest per household in warehouse dashboard API?
- When to ship terrain_map.md only vs require human-edited executive summary before client delivery?
- Sync family-office consideration manifest to InvestmentWarehouse docs/research/ after each DHA run?
