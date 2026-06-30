# Report Writer — Implementation Plan

**Status:** **rw0–rw5 shipped** — `report.build` COMMAND live; external PDF channel via Pandoc
with sha256 pinning; month-end batch fan-out via `workflows.month_end.run_month_end_reporting_batch`.
**rw6 shipped (2026-06-30):** advisor approval gate — external PDF now requires an
APPROVED report-subject approval (recon gate still first). Remaining seams in §7/§16:
rw7 comparability columns, rw8 collector import-cycle fix.
**Date:** 2026-06-30
**Owner:** reporting plane / `warehouse.reporting.report_writer` (new sub-package)
**Inputs:** [`research/report_writing.md`](research/report_writing.md) (reader-first structure,
source → intermediate → deliverable, traceability gates, DHA terrain-map lineage),
[`research/wealth_manager_reports.md`](research/wealth_manager_reports.md) (audience × cadence ×
function taxonomy, client vs internal genre rules),
[`messaging_protocol.md`](messaging_protocol.md) (§5 `report.build`, S1 atomic-op rule),
[`portfolio_manager_implementation.md`](portfolio_manager_implementation.md) (month-end batch
orchestration — `report.build` per household),
[`dev_contract_registry.md`](dev_contract_registry.md) (track registration),
[`heuristics/Cartography.md`](heuristics/Cartography.md) (C4 purposeful omission, C8
self-contained map),
[`heuristics/Libraries.md`](heuristics/Libraries.md) (Lib2 fixed location, Lib6 entry point)

---

## 1. Principle — compile frozen facts; never author numbers

The report writer is a **compiler**, not a prose generator. It assembles **already-computed**
plane outputs into a frozen `ReportBundle` (machine-readable terrain map), then renders
**audience-specific Markdown** from that bundle. Numbers in every exhibit must trace to a
registered function and a `snapshot_id` — polished narrative without traceability is a failure
mode the research docs flag explicitly.

| Layer | Package / `op` | Role | Kind |
| --- | --- | --- | --- |
| **Orchestrator** | `workflows/*`, PM batch | Month-end / event-driven fan-out per household | mixed |
| **Report writer** | `reporting.report_writer` → `report.build` | Collect → bundle → render → write artifacts | COMMAND |
| **Data** | `data.ledger` → `ledger.positions` | Lot-level positions (source of exhibits) | QUERY |
| **Decision** | `policy.check`, `tax.scenario`, analyst legs | IPS drift, tax delta, attribution, NPA | EVALUATE |
| **Research** | `risk.evaluate` | Whole-book risk headline (optional exhibit) | EVALUATE |
| **Execution** | staged orders, recon breaks | Operations section (internal only) | QUERY / COMMAND results |
| **Reporting** | `reporting.performance` | Household P&L snapshot | QUERY (session-backed) |

```text
MONTH-END / AD-HOC TRIGGER
ledger.positions ──► collect_report_bundle(session, household_id, period, as_of)
                         ├── build_household_performance_report   (reporting.performance)
                         ├── build_ips_drift_report               (decision.ips)
                         ├── run_reporting_tax_scenario           (reporting.tax)
                         ├── list_staged_orders                   (execution.oms)
                         └── list_reconciliation_breaks           (execution.recon)
                     → ReportBundle (frozen JSON — terrain map)
                         ├── render_markdown(audience=internal)  → internal.md
                         └── render_markdown(audience=external)  → external.md
                     → runs/reports/{household}/{period}/{snapshot_id}/
ADVISOR REVIEW GATE (human) ──► client delivery (external only)
```

**Internal is source; external is derivative.** Internal packs carry thesis, kill criteria,
trade rationale, open breaks, and binding-constraint detail. External packs apply the wealth-
manager rule: **BLUF first**, exhibit cross-reference ids, separate narrative from numbers,
never place unaudited projections adjacent to realized performance without labelling.

**Messaging contract (§5):** ship exactly one new atomic op — `report.build`. No composite
`report.advise`. Callers that need risk + PM context compose `pm.advise` and `report.build`
with a shared `correlation_id` at the orchestrator layer (same pattern as
`approval.decide → orders.stage`).

**Kind = COMMAND, not QUERY.** `report.build` crosses the protocol's mutation boundary
([`messaging_protocol.md`](messaging_protocol.md) §2): it persists durable artifacts
(`internal.md`, `external.md`, `bundle.json`) and writes an audit row — it produces the
client-of-record document, which is a state change, not a pure read. So it is **gated and
audited** like any COMMAND: the collector's preconditions (IPS + positions present; rw3+
Tier-1 recon breaks ⇒ block external delivery) *are* the gate (the raise is the declaration,
§8), and `write_audit` stamps `snapshot_id` / `household_id` / paths. The pure read — assembling
the in-memory `ReportBundle` — stays inside the handler; we do **not** split a separate
`report.write` op (S1: no second op until a caller needs the bundle without writing). This
supersedes the stale `report.build = QUERY` row in `messaging_protocol.md` §5 (written before the
reporting plane existed); update it on rw1.

---

## 2. Report taxonomy — what v1 covers

Wealth managers ship along three axes (research base rate). v1 intentionally covers **one
cadence** and **two audiences**, with **four functions** — enough for month-end pilot, not the
full 12–20 report-type catalog.

| Axis | v1 in scope | Deferred |
| --- | --- | --- |
| **Audience** | `internal` (IC / advisor), `external` (household principal) | Compliance, regulators, CPAs, estate counsel |
| **Cadence** | `month-end` (`ReportPeriod.month_end(as_of)`) | Onboarding, quarterly letter-only, annual, event-driven |
| **Function** | policy (IPS drift), performance, tax (scenario rollup), operations (orders + breaks) | Full attribution pack, alts K-1 calendar, liquidity runway, scenario one-pager, research terrain |

**Minimum bundles (from research open questions):**

- **Internal (advisor dashboard):** IPS drift + staged trade list + tax delta + open recon
  breaks + frozen `bundle.json`.
- **External (client pack):** BLUF + performance exhibit + policy-alignment summary (breaches
  only) + tax summary (labelled stub when engine is zero) + limitations.

---

## 3. The honesty rule — exhibit liveness

Report writing fails when templates substitute for evidence. Every section declares its data
vintage and source; stubbed upstream engines surface as **limitations**, never silent zeros
presented as estimates.

| # | Exhibit / section | Source | v1 status |
| --- | --- | --- | --- |
| 1 | Performance (MV, unrealized, realized YTD) | `build_household_performance_report` | **live** |
| 2 | After-tax return YTD | reporting performance | **`not_computed`** (field `None`) |
| 3 | IPS drift + concentration | `build_ips_drift_report` | **live** |
| 4 | Tax scenario table | **reporting plane** — `run_reporting_tax_scenario` → `ReportingTaxResult` (see ownership note below) | **partial** — rows live, deltas **stubbed zero** until tax estimate engine ships |
| 5 | Staged orders | `list_staged_orders` | **live** |
| 6 | Open reconciliation breaks (internal only) | `list_reconciliation_breaks` | **live, firm-wide** — `list_reconciliation_breaks` has no `household_id` param and `ReconciliationBreak` carries `account_id` only; breaks shown are whole-firm until the account→household join lands. Must be labelled firm-wide; never rendered in external packs |
| 7 | Attribution residual | `attribution.evaluate` | **live (internal)** — Exhibit D; external omitted rw5 |
| 8 | Risk headline (VaR / ES with explicit α, h) | `risk.evaluate` | **live (internal)** — Exhibit E; external omitted rw5 |
| 9 | Alternatives / K-1 calendar | `data.alternatives` | **`not_computed`** — Addendum C |
| 10 | LLM-drafted executive prose | — | **forbidden in v1** — template strings only; human edit layer is rw3+ |

**Tax exhibit — plane ownership (resolves §3 row 4):** the report writer is a reporting-plane
feature, so its tax exhibit is sourced from the **reporting plane** (`reporting.tax` →
`run_reporting_tax_scenario` → `ReportingTaxResult`, already in `FROZEN_TYPES`) per CLAUDE.md
("reporting plane ships reporting-owned tax scenarios", st6c). It does **not** import the
decision plane's `list_tax_scenarios` / `TaxScenarioRunView` — that would cross a plane boundary
for a read model. If a rollup of *persisted* scenario runs is later needed, add a thin listing
wrapper in `reporting.tax` rather than reaching into `decision.tax`.

**Stated limitations (always rendered in both audiences):**

- Data vintage = `as_of_date`; snapshot = `snapshot_id`.
- Tax deltas may be zero-stubbed — not for client filing.
- Open recon breaks ⇒ exhibits may not match custodian statements.
- Recon breaks listed in internal packs are **firm-wide**, not household-scoped (account→household
  join pending) — do not read them as this household's breaks.
- Pending approvals ⇒ figures subject to change before delivery.

---

## 4. Scope — what ships vs deferred

### In scope (rw0–rw2)

| Item | Rationale |
| --- | --- |
| `ReportBundle`, `ReportPeriod`, `WrittenHouseholdReport` — frozen | Audit/replay terrain map (research: JSON intermediate) |
| `collect_report_bundle(session, household_id, *, period, as_of)` | Single collector; loud failures on missing IPS/positions |
| `render_markdown(bundle, audience)` — internal + external section sets | Research reader-first structure |
| `write_report_bundle` → `runs/reports/.../internal.md`, `external.md`, `bundle.json` | Local artifact store (Phases 0–4 — no object store gate) |
| `report.build` handler + `ReportBuildPayload` | Messaging §5 — unblocks month-end workflow |
| CLI `warehouse report write` | Operator entry point |
| Dashboard **Report writer** panel on `/reporting` | Dashboard-first — snapshot id, BLUF preview, paths |
| Register `ReportBundle`, `WrittenHouseholdReport` in `frozen_registry.py` | Immutability discipline |
| Falsifier tests; extend the existing `reporting` `PlaneTestSlice` in `testing_registry.py` (plane-grained registry — no per-feature slice) | CI gate |
| Exhibit cross-reference ids (`Exhibit A`, `Exhibit B`, …) in external Markdown | Research BLUF + traceability |

### Deferred

| Item | Why |
| --- | --- |
| PDF / HTML / DOCX render (Quarto, Pandoc) | Markdown source is v1; conversion tax deferred (research uncertainty driver) |
| Human-edited executive summary layer before client send | Open question — when terrain_map.md only vs mandated edit |
| Advisor approval gate on `WrittenHouseholdReport` | Needs `approval.create` pattern for documents — TODO open question #9 |
| `report.publish` COMMAND (portal / email) | No delivery channel in Phases 0–4 |
| Per-household recon break filter | Needs account→household join; v1 uses global open breaks (demo-safe) |
| DHA terrain-map quality rubric automation | Research falsifier — manual checklist first |
| LLM draft pass with source grounding | Research: fluency without structure; human sign-off mandatory |
| Full quarterly pack (12–20 report types) | Volume-without-relevance failure mode |
| XBRL / regulatory genres | Out of pilot scope |
| Postgres object-store persistence of bundles | Phase 5 |

---

## 5. Core types

New package: `src/warehouse/reporting/report_writer/`

```python
class ReportAudience(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"

class ReportPeriod(BaseModel):          # frozen
    label: str                          # directory key, e.g. month-end-2026-06-24
    start_date: date | None = None
    end_date: date | None = None

    @classmethod
    def month_end(cls, as_of: date) -> ReportPeriod: ...

class ReportBundle(BaseModel):          # frozen — terrain map
    snapshot_id: str                    # rpt_{uuid}
    household_id: str
    period: ReportPeriod
    as_of_date: date
    generated_at: datetime
    performance: HouseholdPerformanceReport | None
    ips_drift: IpsDriftReport | None
    tax_scenarios: tuple[ReportingTaxResult, ...]   # reporting-plane owned (see §3 note)
    staged_orders: tuple[StagedOrderView, ...]
    pending_approval_count: int
    open_breaks: tuple[ReconciliationBreak, ...]
    limitations: tuple[str, ...]
    data_sources: tuple[str, ...]

class WrittenHouseholdReport(BaseModel):  # frozen — write result
    snapshot_id: str
    household_id: str
    period_label: str
    as_of_date: date
    generated_at: datetime
    output_dir: str
    internal_markdown_path: str
    external_markdown_path: str
    bundle_json_path: str
```

**Payload (messaging):**

```python
class ReportBuildPayload(BaseModel):
    household_id: str
    period_label: str | None = None
    as_of_date: date | None = None
```

Handler returns `WrittenHouseholdReport` (boundary types must be `BaseModel`). Registered as
`Kind.COMMAND` (it writes artifacts + an audit row); the collector preconditions are its gate.

---

## 6. Section taxonomy — internal vs external

Aligned with [`research/report_writing.md`](research/report_writing.md) front matter → summary →
findings by theme → limitations → appendix.

### External (`audience=external`, classification: client-facing)

| Order | Section | Content rule |
| --- | --- | --- |
| 1 | YAML front matter | title, date, audience, classification, period, `snapshot_id` |
| 2 | Executive summary (BLUF) | 2–4 sentences; every numeric claim cites an Exhibit id |
| 3 | Exhibit A — Performance | MV, unrealized, realized YTD; `after_tax` = `n/a` when `None` |
| 4 | Exhibit B — Policy alignment | Breaches only; omit full drift table when in-band |
| 5 | Exhibit C — Tax summary | Scenario table + stub disclaimer |
| 6 | Limitations | Auto-generated from bundle |
| 7 | Appendix pointer | `bundle.json` path |

### Internal (`audience=internal`, classification: IC / advisor)

| Order | Section | Content rule |
| --- | --- | --- |
| 1 | YAML front matter | same + `reporting_window` |
| 2 | Advisory headline | BLUF variant with alert counts |
| 3 | Context | Period-close purpose statement |
| 4 | Exhibit A — Performance | full table |
| 5 | Exhibit B — IPS drift & concentration | full sleeve table + alerts |
| 6 | Exhibit C — Tax scenarios | full table |
| 7 | Execution & operations | pending approvals, staged orders, open breaks (**labelled firm-wide** — not household-scoped yet) |
| 8 | Implications | Static checklist (review alerts, resolve breaks, attestation) |
| 9 | Limitations | same generator as external |
| 10 | Appendix | `bundle.json` + `data_sources` list |

**Omission rule (Cartography C4):** external omits operations detail and full drift grids;
internal omits client-safe tone. Neither omits limitations.

---

## 7. Migration slices — PR sequence + acceptance

Acceptance is by **artifact traceability** (every exhibit number reconciles to bundle JSON) and
**downstream workflow** (month-end batch can call `report.build` without silent skip).

### rw0 — collect + bundle + frozen types *(~1 PR)*

**Goal:** session-backed collector returns a frozen `ReportBundle`; no render yet.

| Task | File(s) |
| --- | --- |
| Models (`ReportBundle`, `ReportPeriod`, `ReportAudience`) | `reporting/report_writer/models.py` |
| `collect_report_bundle` | `reporting/report_writer/collect.py` |
| Register frozen types + samples | `integrity/frozen_registry.py` |
| Unit tests: collector returns drift + performance on demo household | `tests/test_report_writer.py` |
| Falsifier: missing IPS / positions **raises** | `tests/test_report_writer.py` |

**Acceptance:**

- Demo household bundle has non-`None` `performance` and `ips_drift` at `as_of=2026-06-24`.
- `limitations` includes tax-stub note when scenario deltas are zero.
- `pytest tests/test_frozen.py` covers new types.

### rw1 — render + write + `report.build` *(~1 PR)*

**Goal:** Markdown artifacts on disk; messaging op live.

| Task | File(s) |
| --- | --- |
| `render_markdown(bundle, audience)` | `reporting/report_writer/render.py` |
| `write_report_bundle`, `build_and_write_household_reports` | `reporting/report_writer/writer.py` |
| `ReportBuildPayload`, `_report_build` handler, `register("report.build", …)` | `messaging/payloads.py`, `messaging/handlers.py` |
| Update `messaging_protocol.md` §5 — `report.build` **shipped** | docs |
| CLI `warehouse report write` | `cli.py` |
| Round-trip test: `report.build` == direct `build_and_write_household_reports` | `tests/test_report_writer.py` |

**Acceptance:**

- `warehouse report write` creates three files under `runs/reports/{hh}/{period}/{snapshot}/`.
- External Markdown contains `## Executive summary (BLUF)` and `Exhibit A`.
- Internal Markdown contains `## Execution & operations`.
- `dispatch_message("report.build")` returns `WrittenHouseholdReport` with resolvable paths.

### rw2 — dashboard panel + registry *(~1 PR)*

**Goal:** living report status on `/reporting`; track registered.

| Task | File(s) |
| --- | --- |
| `load_report_writer_panel`, `ReportWriterPanelData` | `dashboard/report_writer_data.py` |
| `render_report_writer_section` | `dashboard/render_phase4.py` |
| Wire into `pages/reporting.py` + API JSON | `dashboard/pages/reporting.py`, `server.py` |
| Panel registry: **Report writer** `live` | `phases.py`, `navigation.py` |
| Add `tests/test_report_writer.py` to the `reporting` slice `pytest_paths` (+widen `coverage_glob` to `report_writer`) — `PLANE_TEST_SLICES` is plane-grained (7 fixed slices), not per-feature | `dashboard/testing_registry.py` |
| `report_writer` track in `dev_contract_registry.md` | docs |
| Dashboard falsifier: panel shows snapshot + BLUF or error banner | `tests/test_dashboard.py` |

**Acceptance:**

- `warehouse serve` → `/reporting` shows Report writer panel with snapshot id or loud error.
- Catalog registry links panel to reporting plane.
- No stub badge while backend writes real artifacts.

### rw3 — month-end workflow hook *(~1 PR, after rw1)*

**Goal:** PM batch orchestration can fan out `report.build` per household.

| Task | File(s) |
| --- | --- |
| `run_month_end_reporting(session, household_id, *, as_of)` workflow step | `workflows/month_end.py` *(new)* |
| Wire into "Review all portfolios" batch sketch | `TODO.md`, `portfolio_manager_implementation.md` cross-ref |
| Batch falsifier: failure on one household does not swallow others | `tests/test_report_writer.py` or integration |

**Acceptance:**

- Documented trigger: positions reconciled, marks fresh, period close (`TODO.md`).
- Failures propagate with `household_id` context.

### rw6 — advisor approval gate on client delivery *(initial next step)*

**Goal:** the `ADVISOR REVIEW GATE (human) ──► client delivery` box in §1's dataflow becomes
real. Today external PDF is gated **only** by recon breaks (`_attach_external_pdf`,
`external_pdf_delivery_blocked`); a client-of-record document still ships with no named human
sign-off. This is the persona's **costly-signal axiom** ([`Persona of The Financial Report
Writer.md`](heuristics/Persona%20of%20The%20Financial%20Report%20Writer.md) §6, T3) — the one
claim a report cannot make cheaply is "an advisor stands behind this." Closes open question #9
for documents.

**Design constraint — approval is coupled to optimizations.** `ApprovalRequestRow`
(`infra/db/models.py:297`) has a **required** `optimization_run_id` column; `ApprovalRequestView`,
`create_approval_request`, and `update_approval_status` (`decision/approval/service.py`) all take
it positionally, and OMS `stage_orders_from_approval` **joins on it**
(`execution/oms/service.py`). So a document approval cannot reuse the row as-is. Resolve by
**generalizing the subject** rather than overloading `optimization_run_id`:

- Add `subject_type: ApprovalSubject` (`OPTIMIZATION` | `REPORT`) + `subject_id` to the row;
  make `optimization_run_id` **nullable** and back-fill `subject_type=OPTIMIZATION`,
  `subject_id=optimization_run_id` in an Alembic migration. OMS keeps reading
  `optimization_run_id` (now derived from `subject_id` where `subject_type=OPTIMIZATION`) — no
  OMS behavior change. New frozen/immutable view fields registered if the view is in
  `FROZEN_TYPES`.
- **Messaging (S1):** no new op — reuse `approval.create` / `approval.decide`. Extend
  `ApprovalCreatePayload` with optional `report_snapshot_id` (XOR with `optimization_run_id`;
  raise if both/neither — the raise is the gate, §8). This honors "no second op until a caller
  needs it."

| Task | File(s) |
| --- | --- |
| `ApprovalSubject` enum; nullable `optimization_run_id` + `subject_type`/`subject_id` columns; Alembic migration + back-fill | `decision/approval/__init__.py`, `infra/db/models.py`, `infra/db/migrations/` |
| `create_approval_request` accepts a report subject; `ApprovalRequestView` carries `subject_type`/`subject_id` | `decision/approval/service.py` |
| `ApprovalCreatePayload` optional `report_snapshot_id` (XOR validator) | `messaging/payloads.py` |
| Gate external PDF on an **approved** report-subject request; pending/absent ⇒ block with `reason=awaiting_advisor_approval` (additive to the existing recon-break block) | `reporting/report_writer/writer.py` (`_attach_external_pdf`) |
| CLI `warehouse report approve --snapshot <id>` (+ surface in `warehouse report ...` list) | `cli.py` |
| Dashboard: Report writer panel shows delivery state (`blocked: recon` / `awaiting approval` / `delivered`) | `dashboard/report_writer_data.py`, `dashboard/render_phase4.py` |
| Tests: XOR payload raise; PDF blocked until approved; recon block still wins; OMS join unaffected by migration | `tests/test_report_writer.py`, `tests/test_messaging_handlers.py`, `tests/test_frozen.py` |

**Acceptance:**

- External PDF is **not** written until an `approval.decide(status=APPROVED)` exists for that
  `report_snapshot_id`; before then the panel + audit detail read `awaiting_advisor_approval`.
- Open recon breaks still block first (recon gate precedes approval gate — both must pass).
- `dispatch_message("approval.create", report_snapshot_id=...)` round-trips; passing both
  `optimization_run_id` and `report_snapshot_id` **raises**.
- Existing optimization-approval + OMS staging tests stay green (migration is back-compatible).

### rw7 — comparability columns (prior-period / YoY) *(after rw6)*

**Goal:** satisfy the persona's **comparable, time-adjusted-figures axiom** (§7, Fi2) — "a number
is decision-grade only when placed against the prior period, a benchmark, or a present-value
frame." Today every exhibit (`render.py`) is point-in-time: a performance or drift figure ships
with **no denominator**. Add a prior-period column sourced from the previous `bundle.json` for the
same household.

| Task | File(s) |
| --- | --- |
| `find_prior_bundle(household_id, period)` — load the most recent prior `bundle.json` under `runs/reports/{hh}/` (walk-forward safe: prior `as_of` strictly earlier) | `reporting/report_writer/collect.py` |
| Optional `prior: ReportBundle \| None` reference (or a `comparison` delta snapshot) on `ReportBundle`; frozen | `reporting/report_writer/models.py`, `integrity/frozen_registry.py` |
| Exhibit A/B render Δ vs prior (absolute + %); `n/a` when no prior exists (first report) — never a fabricated zero (honesty rule §3) | `reporting/report_writer/render.py` |
| Limitation line when prior is missing or from a non-adjacent period | `reporting/report_writer/collect.py` |
| Tests: second month-end shows Δ vs first; first-ever report renders `n/a`, not `0`; no lookahead | `tests/test_report_writer.py` |

**Acceptance:**

- The second month-end report for a household shows prior-period and Δ columns on performance +
  drift; the first shows `n/a` with a stated limitation.
- Comparison never reads a bundle with `as_of >=` the current report (walk-forward).

### rw8 — collector import-cycle fix *(hygiene, independent of rw6/rw7)*

**Goal:** remove the recurring cycle risk flagged in `JOURNAL.md` (2026-06-30):
`reporting/report_writer/collect.py` imports from **all five planes at module scope** — the source
of the `daily_refresh` cycle worked around in the rw5 commit. Not reader-facing; fixes a structural
fault before it re-bites.

| Task | File(s) |
| --- | --- |
| Move the cross-plane imports into the collector functions (function-scope) or behind a thin provider indirection, so importing the package no longer pulls all planes | `reporting/report_writer/collect.py` |
| Confirm no import-time cycle: `python -c "import warehouse.workflows.daily_refresh, warehouse.reporting.report_writer"` clean without the rw5 workaround | (verification) |
| Remove the rw5 cycle workaround once the root cause is gone; note in `JOURNAL.md` | rw5-workaround site, `JOURNAL.md` |

**Acceptance:**

- Importing `warehouse.reporting.report_writer` does not transitively import the execution/data
  planes at module load; `pytest` import-graph stays acyclic without the workaround.
- Full gate green (`scripts/ci.sh`).

---

## 8. Protocol invariants — acceptance matrix

| Invariant | Source | Test |
| --- | --- | --- |
| One new atomic op only (`report.build`) | messaging S1 | `test_report_build_registered_once` |
| `report.build` registered as `COMMAND` (writes artifacts + audit) | messaging §2 mutation boundary | `test_report_build_is_command_kind` |
| `report.build` writes an audit row with `snapshot_id` / `household_id` / paths | COMMAND audit rule | `test_report_build_writes_audit` |
| Collector raises on missing IPS / positions (the COMMAND gate) | errors bubble | `test_missing_ips_raises` |
| Bundle is frozen after construction | frozen registry | `tests/test_frozen.py` |
| External BLUF cites exhibit ids | research BLUF | `test_external_markdown_has_bluf_and_exhibits` |
| Tax stub surfaced in limitations | honesty rule #4 | `test_limitations_include_tax_stub_when_zero` |
| `report.build` round-trip == direct call | messaging §5 | `test_report_build_messaging_round_trip` |
| Dashboard shows error, not empty success | dashboard-first | `test_report_writer_panel_error_banner` |
| No LLM-generated figures in v1 | research falsifier | static template render only (code review) |

---

## 9. Test plan summary

| File | Covers |
| --- | --- |
| `tests/test_report_writer.py` | collect, render, write, CLI paths, messaging round-trip, period labels |
| `tests/test_frozen.py` | `ReportBundle`, `WrittenHouseholdReport` immutability |
| `tests/test_messaging_handlers.py` | optional: extend with `report.build` if not duplicated |
| `tests/test_dashboard.py` | reporting page includes Report writer section |

**CI gate:** `ruff` + `mypy` + `pytest`; reporting plane slice includes `test_report_writer.py`.

---

## 10. Integration points (post-rw2)

| Consumer | Integration |
| --- | --- |
| **Month-end batch** (`TODO.md` Review all portfolios) | `ledger.positions` → `report.build` per household after recon green |
| **PM orchestrator** | Optional: attach `WrittenHouseholdReport.snapshot_id` to `AdviceBundle` provenance (additive field — separate PR) |
| **Attribution (rw5)** | `collect_report_bundle` → `evaluate_attribution` with base-regime `RiskAssumptions`; Exhibit D internal only |
| **Risk headline (rw5)** | session → `build_portfolio_from_holdings` + `evaluate_risk`; Exhibit E internal only; `risk_headline_computed` on audit row |
| **Approval gate** | Future: `approval.create` for external Markdown before client portal publish (open question #9). **rw4 seam:** recon gate blocks external PDF when firm-wide breaks are open; advisor document-approval (`ADVISOR REVIEW GATE ──► client delivery`) deferred — needs `approval.create` pattern for documents (today tied to `optimization_run_id`). Code comment at `_attach_external_pdf` in `writer.py`. |
| **Audit log** | `write_audit` on `report.build` with `snapshot_id`, `household_id`, paths |
| **Client portal (Phase 5+)** | Serve frozen PDF generated from `external.md`; portal tile links `bundle.json` exhibits |

---

## 11. Addendum A — render channel (rw4 shipped)

Research minimum tool chain: `terrain_map.json → Quarto template → PDF + approval gate`.

| Stage | Tool | When |
| --- | --- | --- |
| Source | Markdown + YAML front matter | **rw1** |
| Intermediate | `bundle.json` | **rw1** |
| PDF | **Pandoc** (`render_external_pdf` in `pdf.py`) | **rw4 shipped** |
| Client-of-record | Frozen PDF hash pinned to `snapshot_id` on `WrittenHouseholdReport` + `report_build` audit row | **rw4 shipped** |

```text
bundle.json + external.md  →  Pandoc (v1)  →  external.pdf
                                      ↓
                         sha256 pinned on WrittenHouseholdReport + audit
```

**System dependency:** Pandoc must be on `PATH` for PDF render (`brew install pandoc` /
`apt install pandoc`). A PDF engine (wkhtmltopdf, weasyprint, or LaTeX) may also be required.
Phases 0–4: no Docker — operator installs locally.

**CLI:** `warehouse report pdf` re-renders from `--path`, `--household`, or `--snapshot`.

**Risk:** Pandoc table formatting loss on financial exhibits (research uncertainty) — keep
Markdown + JSON as source of truth; PDF is a render artifact only. Hash mismatch ⇒ render
failure, not a stale PDF on disk.

---

## 12. Addendum B — optional exhibits (rw5 shipped)

Pull in when upstream legs are client-safe and version-pinned:

| Exhibit | `op` | rw5 status |
| --- | --- | --- |
| Attribution active-return table | `decision.analyst:evaluate_attribution` | **shipped internal** — Exhibit D; `ACTIVE_RETURN_LABEL`; external deferred |
| Risk headline | `research.risk:evaluate_risk` | **shipped internal** — Exhibit E with explicit `(α, h, unit, mark_source)` |
| PM advisory summary | `pm.advise` | deferred — tax leg stub |
| Scenario one-pager | research scenarios | deferred — no standard export |

Add fields to `ReportBundle` as **optional** frozen snapshots (`attribution`,
`risk_headline`); renderer includes section only when present — Cartography C4.
External packs omit D/E in rw5 (client-safe review deferred).

---

## 13. Addendum C — alternates & tax depth (rw5+, deferred)

UHNW minimum bundle (research): IPS drift + performance + tax + **alts K-1 calendar** +
scenario one-pager.

| Section | Source | Notes |
| --- | --- | --- |
| Alts holdings summary | `list_alternative_holdings` | Data plane live |
| Capital call / distribution calendar | `list_alternative_events` | Event-driven cadence |
| Reporting-tax scenarios | `run_reporting_tax_scenario` | Prefer reporting-plane ownership (st6c) |

Blocked on tax estimate engine for non-zero client tax exhibits — parallel track in `TODO.md`.

---

## 14. Iteration log

| Slice | Status | Notes |
| --- | --- | --- |
| rw0 collect + bundle | shipped | |
| rw1 render + write + `report.build` | shipped | |
| rw2 dashboard + registry | shipped | |
| rw3 month-end workflow | shipped | `run_month_end_reporting_batch`; Tier-1 recon gate on external PDF shipped (firm-wide breaks, no tier field) |
| rw4 PDF channel | shipped | Pandoc v1; `external.pdf` + `external_pdf_sha256`; recon gate blocks PDF not Markdown; `warehouse report pdf` |
| rw5 extended exhibits | shipped | internal Exhibit D (attribution) + E (risk headline); external D/E deferred |
| rw6 advisor approval gate | **shipped** | `ApprovalSubject` (optimization\|report); nullable `optimization_run_id` + `subject_type`/`subject_id` (migration 007, back-filled); `approval.create` reused via XOR `report_snapshot_id`; `approve_and_render_report` produces the PDF only after sign-off (recon gate still precedes); `warehouse report approve`; panel `delivery_state` (delivered\|awaiting_delivery) |
| rw7 comparability columns | **planned** | prior-period / YoY Δ from prior `bundle.json`; `n/a` not `0` on first report |
| rw8 collector import-cycle fix | **planned** | function-scope cross-plane imports; drop rw5 workaround |

---

## 16. Open seams (rw6+) — persona-graded

The three remaining gaps, ranked through [`Persona of The Financial Report
Writer.md`](heuristics/Persona%20of%20The%20Financial%20Report%20Writer.md). Build order is
rw6 → rw7 → rw8; rw8 is independent and can land any time.

| Seam | Persona axiom | Why it matters | Slice |
| --- | --- | --- | --- |
| **Advisor approval gate** | §6 Credibility through costly signal (T3) | A client-of-record document ships with no named human sign-off; the §1 dataflow's review gate is hollow. Highest value; `approval.create` already exists to extend. | **rw6 (shipped)** |
| **Comparability** | §7 Comparable, time-adjusted figures (Fi2) | Exhibits are point-in-time — a figure with no prior-period denominator is not decision-grade. | rw7 |
| **Collector import cycle** | — (engineering hygiene) | `collect.py` imports all five planes at module scope; recurring cycle risk (JOURNAL 2026-06-30). Not reader-facing. | rw8 |

---

## 17. Research falsifiers to monitor

Operationalize before claiming client-value (from DHA runs):

- Clients receiving BLUF letters **with** exhibit cross-reference ids vs narrative-only —
  track meeting-to-action conversion.
- Unified bundle with `snapshot_id` vs legacy multi-PDF — track "numbers don't match"
  complaints at equal recon quality.
- Reports with explicit limitations vs unstructured memos — track complaint rate at equal
  portfolio outcomes.
- Tier 1 recon breaks open ⇒ **block external PDF delivery** (gate rule — **shipped rw4**; firm-wide `list_reconciliation_breaks`, not household-scoped).

When a falsifier fires, downgrade the relevant slice in this plan before expanding report count.
