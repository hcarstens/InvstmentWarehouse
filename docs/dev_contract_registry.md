# Dev Contract Registry

**Purpose:** Single index for scopes, boundaries, and delivery status across woven tracks
(risk API, HNW synthetic, synthetic IPS, decision plane). Prevents contract drift, boundary
bleed, and “always-feasible” features that pass demo but fail pilot.

**Living status (machine-readable):** `src/warehouse/dashboard/risk_build_registry.py`
**Dashboard:** `warehouse serve --risk` → build tracker panel

**Heuristics:** [Libraries.md](heuristics/Libraries.md) (Lib2 fixed location, Lib6 entry point),
[Cartography.md](heuristics/Cartography.md) (C4 purposeful selection, C8 self-contained map)

---

## 1. Three doc layers — which to cite when

| Layer | Role | Authority | Examples |
| --- | --- | --- | --- |
| **Contract** | Boundaries, closed decisions, wire shapes | **Wins on conflict** | `risk_api_contract.md` |
| **Plan** | PR slices, acceptance, dependencies | Execution truth until shipped | `risk_api_implementation_plan.md`, `synthetic_ips_implementation.md` |
| **Research** | Why, credence, falsifiers, open questions | Informs plans only | `research/synthetic_ips.md`, `research/hnw_portfolios.md` |

**Rule:** Implement and review against **Contract + Plan**. Research does not override a closed
decision (contract §8-style tables) without an explicit **contract amendment** (see §6).

**Rule:** Phase roadmap (`TODO.md`) is coarse-grained; track deliverables live in
`risk_build_registry.py`.

---

## 2. Registered tracks

| Track ID | Owner plane | Contract / plan | Status source |
| --- | --- | --- | --- |
| `risk_contract` | Research (risk) | [risk_api_contract.md](risk_api_contract.md) · [risk_api_implementation_plan.md](risk_api_implementation_plan.md) | `RISK_BUILD_DELIVERABLES` |
| `hnw_synthetic` | Research (synthetic) | [research/hnw_portfolios.md](research/hnw_portfolios.md) · risk plan §HNW | `RISK_BUILD_DELIVERABLES` |
| `synthetic_ips` | Decision + synthetic | [research/synthetic_ips.md](research/synthetic_ips.md) · [synthetic_ips_implementation.md](synthetic_ips_implementation.md) | *Add rows when si0a starts* |
| `decision_plane` | Decision | Phase 3 panels · `decision/` package | `TODO.md` Phase 3 ✓ |
| `messaging` | Platform / orchestrator | [messaging_protocol.md](messaging_protocol.md) · [messaging_protocol_implementation.md](messaging_protocol_implementation.md) | m0a–m1 **shipped** (plan iteration log) |
| `portfolio_manager` | Decision (`warehouse.decision.pm`) | [portfolio_manager_implementation.md](portfolio_manager_implementation.md) | pm0–pm2 **shipped** (plan iteration log) |
| `portfolio_analyst` | Decision (`warehouse.decision.analyst`) | [portfolio_analyst_implementation.md](portfolio_analyst_implementation.md) · [heuristics/Mental Model of The Portfolio Analyst.md](heuristics/Mental%20Model%20of%20The%20Portfolio%20Analyst.md) | pa0 **shipped** (attribution + residual; PM 5th leg; falsifiers `tests/test_analyst_attribution.py`, `tests/test_analyst_review.py`); pa1/pa2 planned |

```text
risk_contract v0a–v0c          [shipped]
  └─ hnw_synthetic v1/v1.1     [shipped — rungs 3–4 via emit_hnw_fixture]
       └─ synthetic_ips si0a   [planned — AssetClass unify]
            └─ si0b             [planned — IPS policy fields]
                 └─ si1         [shipped — emit_ips_for_cohort]
                      └─ si2     [shipped — validate_ips + bundle]
                           ├─ si3 [shipped — workflow smokes]
                           └─ si4 [planned — dashboard + DB seed]

messaging m0a (core, plane-free)   [shipped]
  └─ m0b (handlers + payloads)     [shipped]
       ├─ m0c (decouple ⚠)         [shipped — approval/staging decoupled]
       └─ m0d (daily_refresh + events) [shipped — phase-2 event panel]
            └─ m1 (pm.advise + tax.scenario) [shipped — protocol complete]
                 └─ pm0 (narrative + 7-axiom checklist)      [shipped]
                      └─ pm1 (working set + rebalance advisory) [shipped]
                           └─ pm2 (dashboard + registry)        [shipped]
                                └─ portfolio_analyst pa0+        [planned — next milestone]
                                     └─ portfolio_optimization v1 [planned — hard problem]
```

Tax leg held at `$0` stub on purpose (`evaluate_tax_scenario → 0`): a deterministic tax leg
lets synthetic portfolios + IPS stress-test the whole PM flow. Tax estimate engine is a
parallel, non-blocking track — flipping it stub→live does not change the `pm.advise` contract.

`messaging` is a new root — m0a depends on no other track; m0c/m0d/m1 touch the decision,
workflow, and dashboard owners, so coordinate those cells (§3) when they land.

Do not start a slice until `depends_on` slices show `shipped` in the build registry.

---

## 3. Module boundary matrix

Cross-track work must land in **one owner cell**. If none fit, amend this matrix first.

| Module / package | Owns | Must NOT |
| --- | --- | --- |
| `warehouse.research.risk` | `evaluate_risk(request, manifest)` → `RiskResult`; Shape A only | Import `research.synthetic` pipeline, `decision.ips`, `warehouse.data` / `warehouse.infra` in pure core |
| `warehouse.research.synthetic` | Shape B fixtures, cohort priors, IPS emit/validate (planned), provenance | Enforce production IPS; persist trades |
| `warehouse.research.risk.synthetic` | `rung(n)` entry — delegates 3–4 to `emit_hnw_fixture` | Duplicate HNW generator logic |
| `warehouse.decision.ips` | Policy model, drift monitor, store | Generate synthetic fixtures |
| `warehouse.decision.constraints` | Lot-level wash-sale, restricted, do-not-sell | Magic constants divorced from IPS (e.g. hardcoded concentration cap) |
| `warehouse.decision.optimizer` | Trades inside IPS bounds; explainable output | Autonomous execution |
| `warehouse.decision.pm` | `score_pm_axioms` (7-axiom narrative), `build_working_set`; advisory-only composite | Mutate state; persist; import plane cores — reach specialists via `dispatch_message` only |
| `warehouse.messaging.core` | `Message`/`Kind`/`DispatchContext`, `dispatch_message`/`emit_event`, `REGISTRY` | Import any plane (`data`/`decision`/`execution`/`research`/`reporting`) |
| `warehouse.messaging.handlers` | Composition root — register thin `(ctx, payload)` plane wrappers | Move plane logic into wrappers; leak `ctx.session` into an EVALUATE core |
| **Caller** (dashboard, workflow, HTTP adapter) | Compose manifest + IPS + present errors; dispatch cross-plane via `dispatch_message` | Swallow failures; import risk internals bypassing `evaluate_risk` |

**Composition pattern (risk + IPS):**

```text
bundle = emit_synthetic_household(...)     # synthetic — Shape B + IPS
manifest = bundle.fixture.asset_portfolio  # Shape A
risk = evaluate_risk(request, manifest)    # risk — never sees IPS object
drift = build_ips_drift_report(..., bundle.ips)  # decision — caller composes
```

---

## 4. Deliverable registry schema

Each row in `risk_build_registry.py` (`BuildDeliverable`):

| Field | Required | Values / notes |
| --- | --- | --- |
| `id` | yes | Stable slug, e.g. `si0a-asset-class` |
| `track` | yes | `risk_contract` \| `hnw_synthetic` \| `synthetic_ips` \| `decision_plane` \| `messaging` \| `portfolio_manager` \| `portfolio_analyst` |
| `slice` | yes | Plan slice, e.g. `v0a`, `si2` |
| `name` | yes | Short human label |
| `status` | yes | `planned` \| `in_progress` \| `shipped` \| `deferred` \| `retired` |
| `doc_href` | yes | Link to contract or plan anchor |
| `note` | yes | One-line scope reminder |
| `depends_on` | optional | List of `id`s — add when introducing deps |
| `falsifier_test` | optional | pytest node id — **required before `shipped`** for decision/synthetic tracks |

**Status meanings:**

- `planned` — in plan, no code yet
- `in_progress` — active PR branch
- `shipped` — merged; registry + dashboard + falsifier test updated in same PR
- `deferred` — explicitly out of scope; reason in `note`
- `retired` — removed; leave row for history, never delete ids silently

---

## 5. Falsifiers → CI (SDG3)

Prose falsifiers in research docs are not done until wired to tests.

| Falsifier | Track | Test (target) | Status |
| --- | --- | --- | --- |
| Always-feasible IPS | `synthetic_ips` | `test_concentrated_stress_binding_constraints_non_empty` | planned (si2) |
| Risk imports synthetic pipeline in pure core | `risk_contract` | import-lint / `tests/test_risk_service.py` boundary | partial |
| Dashboard stub while registry says shipped | all | build tracker reads registry, not hardcoded | shipped |
| Weight-only book passes lot-level TLH | `hnw_synthetic` | rung 4 + optimizer smoke | partial |
| IPS drift without unfunded alt liquidity stress | `synthetic_ips` | `validate_ips` liquidity check | planned (si2) |

Add a row here when a research doc records a falsifier you intend to enforce.

---

## 6. Amendment protocol

### Add a track

1. Add contract or plan doc (contract if boundaries/wire shapes; plan if execution only).
2. Register track in **§2** of this file.
3. Add `BuildDeliverable` rows (`planned`) in `risk_build_registry.py`.
4. Add boundary rows to **§3** if new package ownership.
5. One line in `JOURNAL.md`.
6. Dashboard panel or extend build tracker — **dashboard-first**.

### Add a deliverable

1. Plan doc slice with acceptance criteria.
2. New `BuildDeliverable` with unique `id`, `depends_on`, target `falsifier_test`.
3. No code until dependencies are `shipped`.

### Ship a deliverable

Same PR must include:

1. `risk_build_registry.py` → `status="shipped"`
2. Contract **review log** line (amend §8 only if decision changed)
3. Falsifier test passing in CI
4. Dashboard reflects registry (not stub)
5. `JOURNAL.md` entry (optional if registry is detailed)

### Change a closed decision

1. Edit contract doc §8 (or add §8 table to new contract).
2. Log in contract review/iteration table with date + rationale.
3. Update this registry §3 if boundaries moved.
4. Migration note in implementation plan if code already shipped.

### Remove or defer

- Set `status="deferred"` or `retired` — **do not delete** `id`.
- Document reason in `note` and plan doc.
- Remove falsifier test only if falsifier no longer applies; never leave shipped + no test.

---

## 7. Document index (Lib2 canonical paths)

| Doc | Layer | Path |
| --- | --- | --- |
| Dev contract registry | Index | `docs/dev_contract_registry.md` *(this file)* |
| Risk API contract | Contract | `docs/risk_api_contract.md` |
| Risk implementation plan | Plan | `docs/risk_api_implementation_plan.md` |
| Synthetic IPS design | Research | `docs/research/synthetic_ips.md` |
| Synthetic IPS implementation | Plan | `docs/synthetic_ips_implementation.md` |
| HNW portfolios / generator axioms | Research | `docs/research/hnw_portfolios.md` |
| Phase roadmap | Roadmap | `TODO.md` |
| Build log | Narrative | `JOURNAL.md` |
| Agent conventions | Conventions | `CLAUDE.md` |

---

## 8. Synthetic IPS deliverables (to register on si0a kickoff)

Copy into `RISK_BUILD_DELIVERABLES` when work starts:

| id | slice | name | depends_on |
| --- | --- | --- | --- |
| `si0a-asset-class` | si0a | AllocationTarget → AssetClass enum | — |
| `si0b-ips-fields` | si0b | IPS concentration / liquidity / turnover fields | si0a-asset-class |
| `si1-emit-ips` | si1 | emit_ips_for_cohort | si0b-ips-fields |
| `si2-validate-ips` | si2 | validate_ips + emit_synthetic_household | si1-emit-ips |
| `si3-workflow-smoke` | si3 | In-process workflow smokes | si2-validate-ips |
| `si4-dashboard-seed` | si4 | Dashboard panel + optional DB seed | si2-validate-ips |

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-06-27 | Initial registry — three layers, boundary matrix, amendment protocol, synthetic_ips track scaffold. |
