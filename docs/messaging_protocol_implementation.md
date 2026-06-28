# Messaging Protocol — Implementation Plan

**Status:** m0a, m0b shipped; m0c–m1 pending
**Date:** 2026-06-28
**Owner:** platform / orchestrator
**Inputs:** [`messaging_protocol.md`](messaging_protocol.md) (contract — wins on conflict),
[`risk_api_contract.md`](risk_api_contract.md) (reference `Evaluate` handler + manifest slicing),
[`dev_contract_registry.md`](dev_contract_registry.md) (track registration, boundary matrix),
[`heuristics/Simplicity.md`](heuristics/Simplicity.md) (S1–S8),
[`heuristics/Mental Model of The Portfolio Manager.md`](heuristics/Mental%20Model%20of%20The%20Portfolio%20Manager.md)

---

## 1. Principle — one wire shape, planes register handlers

Mirror the risk/IPS two-layer split. The **messaging core** owns the envelope, dispatch, and
registry and knows **nothing** about any plane. **Planes own thin `(ctx, payload)` wrappers**; a
single composition module wires them in. The dependency arrow points one way — planes → messaging
core — so there are no import cycles and the core stays portable.

| Layer | Package | Owns | Must NOT |
| --- | --- | --- | --- |
| **Messaging core** | `warehouse.messaging.core` | `Message`, `Kind`, `DispatchContext`, `dispatch_message`, `emit_event`, `REGISTRY` | Import any plane (`data`/`decision`/`execution`/`research`/`reporting`) |
| **Payloads** | `warehouse.messaging.payloads` | Per-`op` request bodies (`RiskEvaluatePayload`, …) | Hold handler logic |
| **Composition root** | `warehouse.messaging.handlers` | Imports plane fns, registers `(payload_type, handler, kind)` | Move plane logic — wrappers are thin |
| **Callers** | `workflows/*`, orchestrator, dashboard, CLI | Build `Message` + `ctx`, call `dispatch_message` | Bypass dispatch for cross-plane calls |

```text
                       register (import-time)
 plane functions  ───────────────────────────►  REGISTRY  ◄─── dispatch_message(ctx, msg)
 (unchanged)        warehouse.messaging.handlers   (core, plane-free)        ▲
                                                                             │ callers
                                            run_daily_refresh / orchestrator ┘
```

Do **not** put plane imports in `core.py` (the analog of "no `warehouse.data` in the risk core").
`handlers.py` is the **only** plane-aware file — the composition root, like `risk/adapters/ledger.py`.

---

## 2. Scope — what ships vs deferred

### In scope (m0–m1)

| Item | Rationale |
| --- | --- |
| `Message`/`Kind`/`DispatchContext` + `dispatch_message`/`emit_event` + typed `REGISTRY` | Contract §3–§4 |
| Thin `(ctx, payload)` wrappers for the §5 catalog (atomic ops) | Contract §5 — no logic moved |
| **Decouple** `approval.decide` ↔ `orders.stage` | Contract §5, §9.3 (committed) |
| First client: `run_daily_refresh` routes `ingest.run` + `ledger.reconcile` | Contract §9.4 |
| Events → phase-2 exception/notification panel | Contract §9.5; dashboard-first |
| `pm.advise` composite + `tax.scenario` (m1) | Contract §4.1, §5 |
| Falsifier tests + `dev_contract_registry` track | Contract §9.6 |

### Deferred (Phase 5 / out-of-process trigger)

| Item | Why |
| --- | --- |
| Idempotency **store** (field reserved only) | No retries in-process → no duplicates (contract §2, §8) |
| Retries / at-least-once / broker / pub-sub infra | `messaging_systems.md` superset — Phase 5 |
| Precondition metadata/DSL | Handlers raise — the raise *is* the declaration (§8) |
| `PROTOCOL_VERSION` as envelope **field**; cross-process wire | Constant now; promotes when a plane goes out-of-process |
| `report.build` handler | Reporting plane not built — `op` stays **planned** |
| Auth/encryption/rate-limit | Single process, single tenant |

---

## 3. Migration slices — PR sequence + acceptance

Acceptance is by **downstream behavior** (a workflow routes through dispatch; the gate still
raises), not by "the module looks done."

### m0a — core + registry *(~1 PR)* — ✅ shipped

**Goal:** the plane-free dispatch substrate; no handlers yet.

| Task | File(s) |
| --- | --- |
| `Message` (frozen), `Kind`, `DispatchContext` (frozen), `PROTOCOL_VERSION` | `messaging/models.py` *(new)* |
| `REGISTRY: dict[str, tuple[type[BaseModel], Handler, Kind]]`, `SUBSCRIBERS` | `messaging/core.py` *(new)* |
| `dispatch_message(ctx, msg)` — registry lookup, payload isinstance check, `add_note` re-raise | `messaging/core.py` |
| `emit_event(ctx, event)` — synchronous fan-out, subscriber failure → `record_exception_panel` | `messaging/core.py` |
| `register(op, payload_type, handler, kind)` / `subscribe(op, fn)` helpers | `messaging/core.py` |
| Freeze + register `Message`, `DispatchContext` | `integrity/frozen_registry.py`, `tests/test_frozen.py` |
| Public surface | `messaging/__init__.py` |

**Acceptance:**

- `dispatch_message(ctx, Message(op="nope", …))` raises `KeyError` (unknown op).
- Payload-type mismatch raises `TypeError` naming expected vs actual.
- `message_id` auto-stamped (uuid4 hex) when empty; `add_note` carries `op`/`correlation_id`/`household_id`.
- `pytest tests/test_frozen.py` green; **no plane imports in `core.py`** (assert in `tests/test_architecture.py`).

### m0b — handler wrappers + payloads *(~1 PR)* — ✅ shipped

**Goal:** every atomic catalog `op` round-trips through dispatch identically to a direct call.

> **Deviation (deliberate):** `__init__.py` does **not** import `handlers` — it stays light so
> that importing `messaging.models` (e.g. from `frozen_registry`) does not transitively drag in
> every plane (S3 isolation). `handlers.py` self-registers on import; composition roots (tests,
> and m0d's `daily_refresh`/dashboard startup) `import warehouse.messaging.handlers` explicitly.
> Result wrappers (`PositionSet`, `TradeValidation`, `ReconcileResult`, `StagedOrders`) added
> because the boundary returns `BaseModel` while some backers return bare `list`/`tuple`.

| Task | File(s) |
| --- | --- |
| Payload models: `RiskEvaluatePayload`, `PolicyCheckPayload`, `OptimizePayload`, `IngestRunPayload`, … | `messaging/payloads.py` *(new)* |
| Register QUERY/EVALUATE wrappers (`ledger.positions`, `risk.evaluate`, `policy.check`, `optimizer.propose`, `trade.validate`) | `messaging/handlers.py` *(new)* |
| Register COMMAND wrappers (`ingest.run`, `ledger.reconcile`, `optimizer.persist`, `approval.create`, `approval.decide`, `orders.stage`) | `messaging/handlers.py` |
| `risk.evaluate` wrapper **ignores `ctx`**, calls pure `evaluate_risk(p.request, p.manifest)` | `messaging/handlers.py` |
| Ensure handlers registered on import (`import warehouse.messaging.handlers`) | `messaging/__init__.py` |

**Acceptance:**

- For each `op`: `dispatch_message(ctx, msg).model_dump() == <direct call>.model_dump()` on the demo
  household (parametrized test).
- `risk.evaluate` handler does **not** touch `ctx.session` (monkeypatch a poisoned session → still works).
- COMMAND wrappers write the same audit rows as today; a forced failure writes `*_failed` then re-raises.

### m0c — decouple approval ↔ staging *(~1 PR — the only behavior change)*

**Goal:** `approval.decide` records the decision only; staging is a separate chained `op`.

| Task | File(s) |
| --- | --- |
| Remove internal `stage_orders_from_approval(...)` call from `update_approval_status` | `decision/approval/service.py` |
| Orchestrator/caller chains `approval.decide → orders.stage` by `correlation_id` | caller (test + `workflows/`) |
| Update phase-4 expectations | `tests/test_phase4.py` |

> ⚠ **BEHAVIOR CHANGE — only slice that touches working code + tests.**
> `test_phase4.py::test_approval_stages_orders` asserts approve ⇒ staged and **will fail** until it
> chains `orders.stage` explicitly; `test_oms_gate_blocks_unapproved_staging` must still pass. Land
> the decouple + test update in **one commit** so the gate is never briefly bypassed.

**Acceptance:**

- After `approval.decide(APPROVED)`, `list_staged_orders` is empty until `orders.stage` is dispatched.
- `orders.stage` on a non-`APPROVED` request still raises (gate intact).
- `pytest tests/test_phase4.py` green with the updated chain.

### m0d — first client + events + dashboard *(~1 PR)*

**Goal:** a real workflow runs through dispatch; events surface on the dashboard.

| Task | File(s) |
| --- | --- |
| `run_daily_refresh` routes `ingest.run` + `ledger.reconcile` via `dispatch_message` (same `ctx.session`, one `correlation_id`) | `workflows/daily_refresh.py` |
| Emit `ingest.completed` (on success), `break.opened` (per new break), `order.filled` | `workflows/daily_refresh.py`, `execution/oms/service.py` |
| `record_exception_panel` + subscriber → phase-2 exception/notification data source | `dashboard/phase2_data.py`, `dashboard/render_phase2.py` |
| Panel shows event stream + subscriber failures (not silenced) | `dashboard/render_phase2.py` |

**Acceptance:**

- `run_daily_refresh` produces identical ledger/recon state as today, now traced by one `correlation_id`.
- A deliberately failing event subscriber appears on the phase-2 panel; the refresh still commits (isolation S3).
- `warehouse serve` phase-2 panel shows `ingest.completed` / `break.opened` from a real run (not a stub).

### m1 — coordinator + tax *(~1 PR)*

**Goal:** the Portfolio Manager tier and the full advisory middle through dispatch.

| Task | File(s) |
| --- | --- |
| `tax.scenario` payload + wrapper (`run_tax_scenario`) | `messaging/payloads.py`, `handlers.py` |
| `pm.advise` composite: nest-dispatch `risk.evaluate` / `optimizer.propose` / `tax.scenario` / `policy.check` with same `ctx` + `correlation_id` → `AdviceBundle` | `messaging/handlers.py` or `decision/pm.py` *(new)* |
| `AdviceBundle` result model | `messaging/payloads.py` |
| Orchestrator rebalance loop chains the §6 sequence | `workflows/` |

**Acceptance:**

- `pm.advise` returns `AdviceBundle{risk, proposal, tax, drift}` and **mutates nothing** (poisoned
  session → still returns, since it nest-dispatches only EVALUATE ops).
- All nested messages share the inbound `correlation_id` (assert in test).
- Full loop `ledger.positions → … → orders.stage → order.filled` runs on the demo household end-to-end.

---

## 4. Module map (target tree)

```text
warehouse/messaging/
  __init__.py      # Message, Kind, DispatchContext, dispatch_message, emit_event, PROTOCOL_VERSION
  core.py          # dispatch_message, emit_event, REGISTRY, SUBSCRIBERS, register/subscribe — PLANE-FREE
  models.py        # Message, Kind, DispatchContext (frozen)
  payloads.py      # RiskEvaluatePayload, PolicyCheckPayload, AdviceBundle, … (may import plane types)
  handlers.py      # composition root — imports plane fns, registers wrappers (ONLY plane-aware file)
```

No changes to plane packages except the **m0c decouple** in `decision/approval/service.py` and the
**m0d** event emissions in `workflows/daily_refresh.py` + `execution/oms/service.py`.

---

## 5. Protocol invariants — acceptance matrix

The messaging analog of the risk plan's SDG matrix: each invariant → the test that proves it.

| Invariant | Source | Test |
| --- | --- | --- |
| One handler per `op`; unknown `op` raises | §4 | `test_messaging_core.py` |
| Payload validated at boundary | §4 | `test_messaging_core.py` |
| Errors raise with context; no error envelope | §4, S7 | `test_messaging_core.py` |
| EVALUATE handler never reads `ctx.session` (purity) | §4, §4.1 | `test_messaging_handlers.py` (poisoned session) |
| COMMAND gate enforced (`orders.stage` ⇒ APPROVED) | §5 | `test_phase4.py` |
| approval/staging decoupled | §5, §9.3 | `test_phase4.py` |
| Event subscriber failure visible, not propagated | §4, S3 | `test_messaging_events.py` |
| Coordinator threads one `correlation_id`; no mutation | §4.1 | `test_messaging_coordinator.py` |
| `Message`/`DispatchContext` immutable | §3, §9.1 | `test_frozen.py` |

---

## 6. Test plan summary

| File | Covers |
| --- | --- |
| `tests/test_messaging_core.py` | dispatch, unknown op, payload mismatch, `message_id` stamp, `add_note` |
| `tests/test_messaging_handlers.py` | per-`op` round-trip == direct call; risk purity |
| `tests/test_messaging_events.py` | subscriber isolation; dashboard visibility |
| `tests/test_messaging_coordinator.py` | `pm.advise` fan-out, correlation chaining, no mutation |
| `tests/test_phase4.py` *(update)* | decouple; gate still raises |
| `tests/test_architecture.py` *(extend)* | `messaging/core.py` imports no plane |
| `tests/test_frozen.py` | `Message`, `DispatchContext` |

**CI gate:** the four falsifiers from contract §9.6 — unknown `op` raises, payload mismatch raises,
`orders.stage` on non-`APPROVED` raises, event subscriber failure visible — must be green.

---

## 7. Dependencies & build order

```text
m0a (core)  →  m0b (handlers + payloads)  →  m0c (decouple)  →  m0d (first client + events)  →  m1 (coordinator + tax)
```

**Parallel-safe:** m0a is independent of all plane work. **m0c** is a pure decision-plane refactor —
it *can* land before messaging exists, but the chained-through-dispatch path needs m0b, so sequence
it after m0b. **m1** needs m0b (atomic ops) and m0d (event plumbing) before the coordinator is useful.

**No `evaluate_risk` signature change.** Messaging wraps it; the risk contract is untouched (the
`risk.evaluate` wrapper is the boundary).

---

## 8. Self-review (plan quality check)

Reviewed against the contract, the two sibling plans, and the codebase 2026-06-28.

### Strengths

- **Mirrors the established two-layer split** — core is plane-free like `warehouse.research.risk`;
  `handlers.py` is the composition root like `adapters/ledger.py`.
- **Additive except m0c** — every other slice registers thin wrappers; no plane logic moves.
- **Falsifiers operationalized** — §9.6 contract checks become a CI gate, not prose.
- **Dashboard-first** — m0d surfaces events on the phase-2 panel; no hidden backend bus.
- **Decouple isolated + flagged** — the one behavior change is its own slice with a same-commit rule.

### Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Import cycle (planes ↔ messaging) | One-way arrow: planes never import messaging; `handlers.py` imports planes, not vice-versa |
| `risk.evaluate` wrapper leaks `ctx.session` into pure core | Wrapper ignores `ctx`; test with a poisoned session asserts purity |
| Decouple silently bypasses the gate mid-refactor | Land decouple + `test_phase4.py` update in one commit (m0c ⚠) |
| Event panel doesn't exist yet | m0d is a dashboard deliverable into the existing phase-2 exception source |
| Naming collision with `infra.notify.dispatch.dispatch_risk_alert` | Use `dispatch_message`/`emit_event` (contract §4) |
| Over-abstraction creep | Core stays ~1 file; non-goals (§2) gate scope; idempotency/precondition are seams, not machinery |
| Nested dispatch shares a `Session` across a long chain | One `ctx.session` per orchestrator run = one unit of work (contract §4.1) — intended, document the transaction boundary |

### Gaps intentionally left open

- Idempotency store + retries (Phase 5 trigger).
- `pm.advise` that *persists* (would make it a COMMAND) — v0 PM is advisory only.
- `report.build` handler (reporting plane unbuilt).
- `PROTOCOL_VERSION` as a wire field (promotes when a plane goes out-of-process).

### Verdict

**Ready to execute** starting with m0a. Estimated **5 PRs**, ~1–2 weeks at current velocity.
Critical path: **m0a → m0b → m0d**; m0c can overlap after m0b; m1 last.

---

## 9. Doc updates on ship

| Doc | Update |
| --- | --- |
| [`messaging_protocol.md`](messaging_protocol.md) | Flip `Status` to **shipped** per slice; tick the §9 migration steps |
| [`dev_contract_registry.md`](dev_contract_registry.md) | Add `messaging` track (§2) + `warehouse.messaging` boundary row (§3); add to the dependency DAG |
| [`TODO.md`](TODO.md) | Add messaging panel + protocol items; link this plan |
| [`risk_api_contract.md`](risk_api_contract.md) | Note `risk.evaluate` is reached via `dispatch_message` (one path, two surfaces) |

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-06-28 | Initial plan from `messaging_protocol.md` (decisions closed §10). Five slices m0a–m1; grounded against `run_daily_refresh`, `infra/notify` collision, phase-2 exception panel, `FROZEN_TYPES`, `dev_contract_registry`. Self-review §8 appended before publish. |
| 2026-06-28 | **m0a shipped.** `warehouse/messaging/{models,core}.py` (plane-free), `__init__` public surface; `Message`/`DispatchContext` frozen + registered. `tests/test_messaging_core.py` (9 tests: unknown-op KeyError, payload-mismatch TypeError, payload type preserved, `add_note` context, event isolation, dup-register, message_id stamp); `test_architecture.py` plane-free assertion. 207 pass, ruff + mypy strict clean. |
| 2026-06-28 | **m0b shipped.** `payloads.py` (11 request bodies + 4 result wrappers), `handlers.py` composition root registering all 11 atomic ops; `Handler` payload typed `Any` for clean wrapper registration. `tests/test_messaging_handlers.py` (8 tests: round-trip == direct for the 5 QUERY/EVALUATE ops, EVALUATE purity via poisoned session, `ingest.run` COMMAND, `orders.stage` gate). Deliberate deviation: `__init__` stays light, handlers self-register on import. 215 pass, ruff + mypy strict clean. |
