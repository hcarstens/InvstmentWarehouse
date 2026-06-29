# Report Writer — Implementation Plan

**Status:** **planned** — `report.build` remains **planned** in
[`messaging_protocol.md`](messaging_protocol.md) §5; reporting plane ships performance +
reporting-owned tax scenarios but no household report pack yet.
**Date:** 2026-06-29
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
| 7 | Attribution residual | `attribution.evaluate` | **`not_computed`** in v1 — internal Addendum B |
| 8 | Risk headline (VaR / ES with explicit α, h) | `risk.evaluate` | **`not_computed`** in v1 — Addendum B |
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
| **Approval gate** | Future: `approval.create` for external Markdown before client portal publish (open question #9) |
| **Audit log** | `write_audit` on `report.build` with `snapshot_id`, `household_id`, paths |
| **Client portal (Phase 5+)** | Serve frozen PDF generated from `external.md`; portal tile links `bundle.json` exhibits |

---

## 11. Addendum A — render channel upgrade (rw4+, deferred)

Research minimum tool chain: `terrain_map.json → Quarto template → PDF + approval gate`.

| Stage | Tool | When |
| --- | --- | --- |
| Source | Markdown + YAML front matter | **rw1** |
| Intermediate | `bundle.json` | **rw1** |
| PDF | Quarto or Pandoc CI job | rw4 — after advisor gate design |
| Client-of-record | Frozen PDF hash pinned to `snapshot_id` | rw4+ |

**Risk:** Pandoc table formatting loss on financial exhibits (research uncertainty) — keep
Markdown + JSON as source of truth; PDF is a render artifact.

---

## 12. Addendum B — optional exhibits (rw4+, deferred)

Pull in when upstream legs are client-safe and version-pinned:

| Exhibit | `op` | Blocker |
| --- | --- | --- |
| Attribution residual table | `attribution.evaluate` | Needs class-expected honesty labelling in client copy |
| Risk headline | `risk.evaluate` | Must print explicit `(α, h)` per research tail-risk unit note |
| PM advisory summary | `pm.advise` | Tax leg stub — external pack must badge `tax: stub` |
| Scenario one-pager | research scenarios | No standard scenario summary export yet |

Add fields to `ReportBundle` as **optional tuples**; renderer includes section only when
present — Cartography C4.

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
| rw0 collect + bundle | planned | |
| rw1 render + write + `report.build` | planned | Unblocks messaging §5 planned → shipped |
| rw2 dashboard + registry | planned | |
| rw3 month-end workflow | planned | Depends rw1 |
| rw4 PDF channel | deferred | Quarto/Pandoc |
| rw5 extended exhibits | deferred | attribution, risk, alts |

---

## 15. Research falsifiers to monitor

Operationalize before claiming client-value (from DHA runs):

- Clients receiving BLUF letters **with** exhibit cross-reference ids vs narrative-only —
  track meeting-to-action conversion.
- Unified bundle with `snapshot_id` vs legacy multi-PDF — track "numbers don't match"
  complaints at equal recon quality.
- Reports with explicit limitations vs unstructured memos — track complaint rate at equal
  portfolio outcomes.
- Tier 1 recon breaks open ⇒ **block external delivery** (gate rule — implement in rw3+).

When a falsifier fires, downgrade the relevant slice in this plan before expanding report count.
