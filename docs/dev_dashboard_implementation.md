# Dev Dashboard — Multi-Page Implementation Plan

**Status:** dd3 shipped (decision plane page); dd4 pending
**Date:** 2026-06-28
**Owner:** platform / `warehouse.dashboard`
**Purpose:** Break the thin dashboard into plane-scoped pages that mirror repo structure,
linked from a single catalog entry point. The dashboard remains the living dev progress
report — not a slide deck.

**Inputs:**

- [`heuristics/Simplicity.md`](heuristics/Simplicity.md) (S1–S8)
- [`heuristics/Libraries.md`](heuristics/Libraries.md) (Lib1–Lib6)
- [`heuristics/Cartography.md`](heuristics/Cartography.md) (C1–C8)
- [`dev_contract_registry.md`](dev_contract_registry.md) (Lib6 entry point, Lib2 fixed URLs)
- [`TODO.md`](../TODO.md) (phase ↔ panel registry — keep `phases.py` in sync)
- Current implementation: `src/warehouse/dashboard/server.py` (`render_html` ≈ 500 lines, 30+
  sections on one scroll)

---

## 1. Problem — the monolith stopped being a map

`warehouse serve` renders **every** live panel on `/`: Phase 0 meta, Phase 1 schema views,
Phase 2 positions + risk, Phase 3 decision + PM/analyst depth, Phase 4 execution, plus
orchestrator gates — one 30s auto-refresh page.

That violates the heuristics we already cite elsewhere:

| Axiom | Symptom today |
| --- | --- |
| **S1** Parsimony | One page loads 15+ data sources per refresh |
| **S2** Singular function | `/` is catalog, data browser, risk report, and PM advisory at once |
| **S3** Isolation | A Phase 3 load error sits above Phase 1 tables; unrelated panels share fate |
| **S4** Transparency | Hard to answer “what is the decision plane status?” without scrolling |
| **S6** Low activation | First paint waits on slowest loader (phase3 + phase4 + advisory chain) |
| **S7** Error recognition | Errors exist but drown in volume |
| **C4** Purposeful selection | No scale-appropriate omission — everything at 1:1 detail |
| **C6** Visual hierarchy | Meta tables (roadmap, workflows) compete with live operational panels |
| **Lib1** Collocation | Panels for `warehouse.data` are interleaved with `warehouse.decision` |
| **Lib6** Single entry | Footer links to JSON APIs, not to human-facing plane pages |

The `/risk` landing page is the counterexample: one purpose, one load path, linkable.
Replicate that pattern across the repo’s operational planes.

---

## 2. Design principle — catalog + plane maps

### 2.1 Projection choice (C1, C4)

The dashboard’s job is **dev progress and status**, not operations at trade-desk granularity.
Accept distortion:

- **Catalog (`/`)** — orientation, rollup metrics, plane readiness, phase progress, infra
  error count, links outward. Omit panel-level tables.
- **Plane pages** — live panels for one package family. Omit cross-plane meta (roadmap,
  workflow catalog).
- **`/risk`** — unchanged role: research-track build registry + live manifest smoke (already
  a separate projection).

Do not build a 1:1 scroll of the entire codebase (C4 — avoid the 1:1 map).

### 2.2 Fixed locations (Lib2, C3)

Every page gets one canonical path. No duplicate content at `/dashboard` and `/`.

| Path | Map | Package(s) | Primary audience question |
| --- | --- | --- | --- |
| `/` | **Catalog** | platform shell | “Where am I in the build? What is broken?” |
| `/data` | Data plane | `warehouse.data` | “Can we ingest, store, and browse the book?” |
| `/research` | Research plane | `warehouse.research` | “Do sims, risk, and backtests run?” |
| `/decision` | Decision plane | `warehouse.decision` | “Do IPS, optimizer, PM, and analyst legs fire?” |
| `/execution` | Execution plane | `warehouse.execution` | “Do recon, refresh, and OMS paths work?” |
| `/reporting` | Reporting plane | `warehouse.reporting` | “What reporting panels are live vs stub?” |
| `/infra` | Infrastructure | `warehouse.infra` | “Are SQLite, paths, jobs, and audit healthy?” |
| `/risk` | Risk build tracker | `warehouse.research.risk` + registry | “Where is the risk contract on the rung ladder?” |

Phase numbers remain in `phases.py` for **roadmap tracking**; navigation is by **plane**, not
phase (Lib4 — one vocabulary: “decision plane”, not “Phase 3 dashboard”).

### 2.3 Citation chaining (Lib5, C8)

Every page is self-contained (C8) within its scope:

- **Header:** plane name, package path, readiness badge from `status.PLANES`
- **Nav bar:** catalog + all plane links; current page highlighted (C7 orientation)
- **Body:** that plane’s panels only
- **Footer:** `generated_at`, auto-refresh note, JSON API link for *this* page, “↑ Catalog”

Catalog links **down** to planes; plane footers link **up** to catalog and **sideways** to
related planes (e.g. Decision → Research for backtest context). Panel registry on the catalog
lists every panel with a deep link to its owning plane page (Lib5).

---

## 3. Panel migration — monolith → plane pages

Keep existing `*_data.py` / `render_*.py` modules. **Move assembly**, not business logic.

| Panel (from `phases.py`) | Today | Target page |
| --- | --- | --- |
| Platform overview | `/` metrics strip | `/` catalog |
| Phase roadmap | `/` | `/` catalog |
| Plane readiness | `/` | `/` catalog (plane cards) |
| Workflow catalog | `/` | `/` catalog |
| Dashboard panels (registry) | `/` | `/` catalog (link column → plane) |
| Infra health | `/` | `/` catalog summary + `/infra` detail |
| Entity graph view | `/` | `/data` |
| Security master browser | `/` | `/data` |
| Schema status | `/` | `/data` |
| Ingest status | `/` | `/data` |
| Positions & lots | `/` | `/data` |
| Custodian selector | `/` | `/data` |
| Alternatives panel | `/` | `/data` (alt sub-ledger lives in data plane) |
| Risk manifest | `/` | `/research` |
| Risk build tracker | `/risk` | `/research` (embed summary + link to `/risk`) |
| Backtest results | `/` | `/research` |
| IPS drift monitor | `/` | `/decision` |
| Optimizer proposals | `/` | `/decision` |
| Approval queue | `/` | `/decision` |
| Constraint binding report | `/` | `/decision` |
| Synthetic IPS binding matrix | `/` | `/decision` |
| Advisory bundle (`pm.advise`) | `/` | `/decision` |
| Attribution residuals | `/` | `/decision` |
| Kill-criteria watch | `/` | `/decision` |
| Non-performing-asset flags | `/` | `/decision` |
| Reconciliation queue | `/` | `/execution` |
| Daily refresh timeline | `/` | `/execution` |
| Staged orders | `/` | `/execution` |
| Solver comparison | `/` | `/execution` |
| Audit log stream | `/` | `/infra` (owner: `warehouse.infra.audit`) |
| Tax scenario panel | `/` | `/reporting` |
| Office Manager gate | `/` | `/` catalog (orchestrator — one panel; not worth a page) |

**Load rule (S3):** a plane page calls only its loaders. Shared context (e.g.
`household_id` from phase2) is resolved inside that page’s composition root — not by loading
the full monolith graph.

---

## 4. Target architecture

### 4.1 Module layout (HLib1 collocation)

```text
src/warehouse/dashboard/
  navigation.py      # PAGES registry — path, title, package, panel ids (Lib2, Lib4)
  layout.py            # shared CSS, nav bar, page wrapper, error banner helper
  catalog.py           # render_catalog() — status rollup + plane cards + registry
  pages/
    data.py            # compose phase1 + ingest/positions/custodian/alts fragments
    research.py        # risk section + backtest; link card to /risk
    decision.py        # phase3 + advisory + analyst + npa fragments
    execution.py       # recon + refresh + OMS + solver
    reporting.py       # tax scenario (+ future performance panels)
    infra.py           # infra_checks detail + audit log
  server.py            # thin router: path → render function
  status.py            # unchanged + optional page_summaries() for catalog
  phases.py            # unchanged — still synced with TODO.md
  *_data.py            # unchanged loaders
  render_*.py          # unchanged HTML fragments
```

`render_html()` in `server.py` is **retired** after dd5 — not kept as a hidden code path (S1).

### 4.2 Navigation registry (Lib4)

Single source of truth for URLs and panel ownership:

```python
@dataclass(frozen=True)
class DashboardPage:
    page_id: str          # "data" | "research" | ...
    path: str             # "/data"
    title: str            # "Data plane"
    package: str          # "warehouse.data"
    panel_names: tuple[str, ...]  # names matching phases.py DashboardPanel.name
```

`navigation.py` exports `PAGES`, `page_for_panel(name)`, `plane_readiness(package)`.
Adding a panel = one row in `phases.py` + one entry in the page’s `panel_names` tuple +
render call in the page module — three fixed locations (Lib2).

### 4.3 HTTP surface

| Method | Path | Response |
| --- | --- | --- |
| GET | `/` | Catalog HTML |
| GET | `/data` … `/infra` | Plane HTML |
| GET | `/risk`, `/risk/` | Risk build HTML (unchanged) |
| GET | `/api/status` | Full `StatusReport` JSON (unchanged — automation entry) |
| GET | `/api/pages/{page_id}` | **New** — JSON mirror of one plane page’s data bundle |
| GET | `/api/phase1` … `/api/phase4` | Keep through dd5; deprecate in favor of `/api/pages/*` in dd6 |
| GET | `/api/health` | Unchanged |

`/dashboard` → **301 to `/`** (Lib2 — one catalog URL).

Query params stay page-local:

- `/data?q=` — security master search
- `/data?custodian=` — custodian filter (relocate from `/`)

### 4.4 Catalog page content (Lib6)

The catalog answers four questions in order (C6 hierarchy):

1. **Health** — infra error banner if `infra_error_count > 0`; link to `/infra`
2. **Progress** — live vs planned panel counts; phase table (compact)
3. **Planes** — five cards: readiness badge, one-line note from `PLANES`, link to page,
   count of live panels on that page
4. **Registry** — full panel table with columns: Panel · Phase · Status · **Page** (link)

Below: workflow catalog (compact), north star + build order, orchestrator gate (single section).

No entity tables, no positions, no optimizer output on `/` (C4).

### 4.5 Shared layout (C5, C7, C8)

Extract CSS from `render_html()` into `layout.py` once. Legend (C5):

| Symbol | Meaning |
| --- | --- |
| Green badge | live / ok / complete |
| Amber badge | stub / partial / in_progress / warn |
| Gray badge | planned / skipped / muted |
| Red badge | error |
| Nav highlight | you are here |

Nav order matches build order and `status.PLANES` declaration order (C7):

`Catalog · Data · Research · Decision · Execution · Reporting · Infra · Risk build`

---

## 5. Error and status behavior (S7)

- Each page loader returns a typed bundle with optional `error: str | None` (existing pattern).
- Plane page: error banner **above** nav content, panel sections still render what loaded (no
  silent empty state when sibling failed).
- Catalog: aggregate `page_errors: list[PageError]` from lightweight probes or cached results
  — show “Decision plane: load failed” with link to `/decision`, not a stack trace on `/`.
- JSON APIs: keep `503` when page bundle has `error` (existing phase API behavior).
- Never swallow loader exceptions (CLAUDE.md) — propagate into `error` field and banner.

---

## 6. Implementation slices

Mirror other plan docs: small PRs, dashboard-visible each step.

### dd0 — Shell + catalog *(~1 PR)*

| Task | Notes |
| --- | --- |
| Add `navigation.py`, `layout.py`, `catalog.py` | No panel moves yet |
| Extract shared CSS + nav to `layout.wrap(title, body, active_page=...)` | |
| Change `/` to render catalog only | Meta sections from old footer move up |
| `/dashboard` → redirect `/` | |
| Tests: `test_catalog_renders_plane_links`, nav contains all `PAGES` | |

**Acceptance:** `warehouse serve` → catalog with plane cards and panel registry links (links
404 until dd1–dd4 — acceptable if hrefs are correct). `/api/status` unchanged. CI green.

### dd1 — Data plane page *(~1 PR)*

| Task | Notes |
| --- | --- |
| `pages/data.py` — phase1 + phase2 ingest/positions + phase4 custodian/alts | |
| Route `GET /data` | |
| Add `GET /api/pages/data` | Composes existing pydantic models |
| Wire catalog registry links | |

**Acceptance:** entity graph, security master search, schema, ingest, positions, custodian,
alts visible on `/data` only. Falsifier: `test_data_page_loads` asserts sections present;
`test_catalog_does_not_contain_entity_graph`.

### dd2 — Research plane page *(~1 PR)*

| Task | Notes |
| --- | --- |
| `pages/research.py` — risk manifest + phase3 backtest + `/risk` link card | Reuse `render_risk_section` |
| Route `GET /research`, `GET /api/pages/research` | |

**Acceptance:** risk manifest + backtest on `/research`; `/risk` still serves build tracker.

### dd3 — Decision plane page *(~1 PR)*

| Task | Notes |
| --- | --- |
| `pages/decision.py` — phase3 + advisory + analyst + npa | Largest HTML bundle |
| Route `GET /decision`, `GET /api/pages/decision` | |

**Acceptance:** all Phase 3 panels + PM/analyst sections; `test_decision_page_loads` covers
`pm.advise`, kill-criteria, NPA (migrate assertions from `test_render_html_contains_key_sections`).

### dd4 — Execution, reporting, infra *(~1 PR)*

| Task | Notes |
| --- | --- |
| `pages/execution.py` — recon, refresh, staged orders, solver | |
| `pages/reporting.py` — tax scenario | Stub honestly labeled |
| `pages/infra.py` — infra checks + audit log | |
| Routes + `/api/pages/*` for each | |
| Orchestrator section on catalog | |

**Acceptance:** each page loads independently; catalog infra summary links to `/infra`.

### dd5 — Remove monolith + registry *(~1 PR)*

| Task | Notes |
| --- | --- |
| Delete `render_html()` and monolithic assembly in `server.py` | |
| Update `tests/test_dashboard.py` — page-scoped tests replace monolith test | |
| Register track `dev_dashboard` in `dev_contract_registry.md` §2 | |
| Update `CLAUDE.md` / `TODO.md` dashboard-first bullets with page URLs | |
| `warehouse serve` startup prints catalog + plane URLs | S6 |

**Acceptance:** no code path renders the all-in-one page. Panel count on catalog matches
`phases.py`. `live_panel_count` unchanged.

### dd6 — API consolidation *(optional follow-up)*

| Task | Notes |
| --- | --- |
| Deprecation notice on `/api/phaseN` responses | `Deprecation: use /api/pages/data` |
| Document JSON map in this file §4.3 | |

---

## 7. Testing strategy

| Test | Intent |
| --- | --- |
| `test_catalog_renders_all_plane_links` | Lib6 — every `PAGES.path` linked from `/` |
| `test_page_{id}_loads` per plane | S7 — loader errors surface in HTML |
| `test_catalog_excludes_{plane}_detail` | C4 — no bleed |
| `test_panel_registry_links_resolve` | Each live panel href returns 200 |
| `test_api_pages_{id}` | JSON parity with HTML data |
| HTTP integration (pattern from `test_risk_api.py`) | One test hits `/decision` via `DashboardHandler` |

Do not assert the monolith after dd5. Keep `build_status_report()` tests unchanged.

---

## 8. Registry and doc sync

When a slice ships:

1. Update `phases.py` only if panel ownership or status changes (usually unchanged in dd0–dd5).
2. Add `dev_dashboard` row to [`dev_contract_registry.md`](dev_contract_registry.md) §2:
   owner = platform, status source = `phases.py` + navigation registry.
3. Dashboard-first rule in `TODO.md` becomes: “visible at `warehouse serve` → `/data` (etc.)”
   per plane deliverable — not “everything on `/`”.
4. New panels: register in `phases.py`, `navigation.py` panel list, plane `pages/*.py` render
   call, catalog link column — **four fixed steps** (Lib2).

---

## 9. Non-goals (this plan)

| Item | Why deferred |
| --- | --- |
| SPA / frontend framework | S6 — stdlib HTTP + HTML fragments work; zero new deps |
| Auth / multi-tenant routing | Phase 5 pilot concern |
| Real-time push / websockets | 30s meta refresh stays |
| Merging `/risk` into `/research` | `/risk` is already a successful single-purpose map; link, don’t fuse |
| Rewriting `render_*.py` templates | Move fragments, don’t redesign UI |
| Docker / Postgres panels | Phase 5 — `/infra` will gain rows when shipped |

---

## 10. Success criteria

The split is done when:

1. A developer opens `http://127.0.0.1:8765/` and reaches any live panel in **≤2 clicks**
   (catalog → plane → section anchor optional).
2. Each plane page loads **only** its loaders (measurable: dd5 can add a dev-only timing log).
3. `curl /api/status` still drives automation; plane JSON available at `/api/pages/{id}`.
4. Heuristic checklist passes:

| Axiom | Pass condition |
| --- | --- |
| S1 | No monolithic `render_html` |
| S2 | Each route one plane (except catalog + `/risk`) |
| S3 | Plane loader failure does not block other routes |
| S4 | Nav bar shows full site structure on every page |
| S6 | Catalog first paint avoids decision-chain loaders |
| S7 | Errors visible on owning page + summarized on catalog |
| Lib2 | Stable paths documented in §2.2 |
| Lib5 | Panel registry links to plane pages |
| Lib6 | `/` is the only entry point linked from CLI startup |
| C4 | Catalog omits operational detail tables |
| C8 | Each plane page footer includes API link + timestamp |

---

## 11. Related docs

- [`dev_contract_registry.md`](dev_contract_registry.md) — track index; register `dev_dashboard` at dd5
- [`risk_api_implementation_plan.md`](risk_api_implementation_plan.md) — `/risk` build tracker (keep)
- [`portfolio_manager_implementation.md`](portfolio_manager_implementation.md) — decision panels on `/decision`
- [`portfolio_analyst_implementation.md`](portfolio_analyst_implementation.md) — analyst panels on `/decision`
- [`CLAUDE.md`](../CLAUDE.md) — dashboard-first rule (update URLs at dd5)
