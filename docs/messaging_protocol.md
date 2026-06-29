# Messaging Protocol — In-Process Request Taxonomy

**Status:** v0 shipped (m0a–m1) — `warehouse.messaging` live; daily_refresh + rebalance loop route through `dispatch_message`
**Owner:** platform / orchestrator
**Related:** `docs/research/messaging_systems.md` (out-of-process superset),
`docs/heuristics/Simplicity.md`, `docs/heuristics/Mental Model of The Portfolio Manager.md`,
`docs/risk_api_contract.md` (the reference `Evaluate` handler), `docs/dev_contract_registry.md`

> **One idea:** every inter-module interaction is a typed `Message` with a `kind`, dispatched
> in-process to one handler that returns a typed result or **raises**. No broker, no queue, no
> error envelope. The protocol is a *classification of requests*, not an infrastructure.

> **Adaptability principle — seams now, machinery later.** An adaptable protocol reserves cheap
> *evolution seams* (typed registry, `protocol_version`, `idempotency_key` field, a dispatch
> context) and **defers machinery until the need is real** (idempotency store, retries, broker,
> precondition DSL). Simplicity (S1/S6) and the PM model (*size to the actual risk; robustness
> beats optimality*) point the same way — don't insure against a regime you're not in. This is the
> same "reserve the slot, defer the engine" move as the `deltas` field in `risk_api_contract.md`.

---

## 1. Scope — the in-process subset

`messaging_systems.md` describes the full out-of-process design (brokers, persistence,
delivery guarantees, service mesh). The repo is a single Python process with no external
services through Phase 4, so this protocol keeps only what an in-process monolith needs and
**defers the rest to Phase 5** — exactly the Postgres/Redis deferral the repo already uses.

| Keep (in-process) | Drop → Phase 5 (out-of-process) |
| --- | --- |
| Typed envelope, request-reply, fire-and-forget events | Broker, persistent queues, DLQ |
| `correlation_id` tracing | At-least-once / exactly-once, retries, backoff |
| Pydantic-validated payloads (schema = the contract) | Circuit breakers, backpressure, flow control |
| Errors **raise** (the repo's "errors bubble" rule) | Standardized error envelopes, remediation codes |
| In-process dispatch registry (`op → handler`) | Service discovery, mesh, capability negotiation |
| Single tenant, single process | Auth tokens, in-queue encryption, rate limiting |

## 2. The four request kinds (the taxonomy)

Every message is exactly one `kind`. The kind is the protocol — it determines handling, and the
cut that matters is the **mutation boundary**.

```python
class Kind(StrEnum):
    QUERY    = "query"     # read stored state        — pure, no mutation, raises on error
    EVALUATE = "evaluate"  # compute over passed input — pure, no mutation, raises on error
    COMMAND  = "command"   # change state             — gated + audited, idempotency seam reserved
    EVENT    = "event"     # notify of a past change  — fire-and-forget, no reply
```

- **`QUERY` vs `EVALUATE`** — both pure and reply-bearing; they differ in *where the data comes
  from*. `QUERY` reads the ledger/store (needs a `Session`); `EVALUATE` is a standalone
  computation over a payload it was handed (the risk module — pure, no DB — is the canonical
  `Evaluate`, and **must never receive a `Session`**, see §4).
- **`COMMAND`** is the only kind that mutates. It carries the cost: a precondition gate (enforced
  by the handler raising) and an audit row. An `idempotency_key` field is **reserved** for Phase-5
  retry safety; v0 builds no store and relies on *natural* idempotency where it exists (§5).
- **`EVENT`** is past-tense. It announces a mutation that already succeeded; subscribers react but
  cannot fail the emitter.

> Collapse rule: `QUERY` + `EVALUATE` are *advisory* (free); `COMMAND` is *acting* (gated);
> `EVENT` is *notification*. If you only remember one line, remember that.

## 3. The envelope + context (two types)

The wire envelope routes/traces/scopes; the **`DispatchContext`** carries the unit of work and is
**not** on the wire (it can't cross a process boundary — which is exactly why it's separate, and
the seam that lets Phase 5 swap the backing).

```python
class Message(BaseModel):                  # frozen=True; registered in FROZEN_TYPES
    op: str                       # "risk.evaluate" — routes to exactly one handler
    kind: Kind
    payload: BaseModel            # the typed request body (the actual contract)
    correlation_id: str           # caller-generated uuid4 hex — trace one workflow across planes
    household_id: str | None = None       # the scoping key the repo threads everywhere
    message_id: str = ""          # stamped by dispatch (uuid4 hex) if empty
    idempotency_key: str | None = None    # COMMAND-only seam — reserved; no store in v0

PROTOCOL_VERSION = "0"            # module constant; promotes to an envelope field at Phase 5
                                  # (cross-process wire versioning) — the adaptability seam

@dataclass(frozen=True)
class DispatchContext:            # the unit of work — NOT part of the wire envelope
    session: Session
    actor_id: str = "system:messaging"
    settings: Settings | None = None      # resolved inside dispatch if None
```

Six core envelope fields + one reserved COMMAND seam. Pruned from `messaging_systems.md`'s
~10-field envelope: timestamps (the audit log stamps), priority/QoS and TTL (no queue — calls are
synchronous), physical sender/recipient (dispatch by `op`), security tokens (single process).

## 4. Dispatch & errors

Registry entries are **triples** `(payload_type, handler, kind)` — payload validated at the
boundary, so internals can change without breaking callers (the adaptability seam, and S5/S7).

```python
Handler = Callable[[DispatchContext, BaseModel], BaseModel]
REGISTRY: dict[str, tuple[type[BaseModel], Handler, Kind]] = {}   # op → (payload_type, handler, kind)

def dispatch_message(ctx: DispatchContext, msg: Message) -> BaseModel:
    payload_type, handler, _kind = REGISTRY[msg.op]      # KeyError → unknown op (raises)
    if not isinstance(msg.payload, payload_type):
        raise TypeError(f"{msg.op}: payload {type(msg.payload).__name__}, expected {payload_type.__name__}")
    try:
        return handler(ctx, msg.payload)                 # typed result, or it RAISES
    except Exception as err:
        err.add_note(f"op={msg.op} correlation_id={msg.correlation_id} household_id={msg.household_id}")
        raise

def emit_event(ctx: DispatchContext, event: Message) -> None:     # EVENT only — synchronous fan-out
    for sub in SUBSCRIBERS.get(event.op, ()):
        try:
            sub(ctx, event.payload)
        except Exception as err:                         # isolation (S3): a reacting subscriber
            record_exception_panel(ctx, event.op, err)   # must not fail the committed emitter —
                                                         # surfaced on the dashboard, never silenced
```

- **Uniform `(ctx, payload)` signature — but EVALUATE handlers ignore `ctx`.** The `risk.evaluate`
  wrapper is `def _risk_evaluate(ctx, p): return evaluate_risk(p.request, p.manifest)` — `ctx` is
  unused and the **pure risk core never sees a `Session`**. The wrapper lives at the messaging
  edge, not in the core; the standalone-module boundary holds.
- **No error envelope.** A failed `QUERY`/`EVALUATE`/`COMMAND` raises; the exception *is* the error
  protocol (S7). `dispatch_message` attaches `op`/`correlation_id`/`household_id` via
  `add_note` and re-raises — never swallows.
- **Commands** write an audit row on success and a `*_failed` row before re-raising (repo audit +
  "dashboard must show failures" rules).
- **Naming.** `dispatch_message` / `emit_event` (not `dispatch`/`emit`) to avoid collision with
  `warehouse.infra.notify.dispatch` (outbound webhook alerts — a different concern).

### 4.1 Nested dispatch & coordinator handlers (the Portfolio Manager tier)

A handler may itself call `dispatch_message` — this is how a **coordinator** (the
`repo_structure.pdf` **Portfolio Manager**) fans out to sub-ops. The diagram's two tiers
(ORCHESTRATOR → PORTFOLIO MANAGER → {analyst, optimizer, tax, risk}) are *allowed without a new
`kind`* — a coordinator is just a handler that dispatches. Rules:

- **Same `ctx`, same `correlation_id`.** A coordinator threads the inbound `ctx` and
  `correlation_id` into every nested message, so the whole fan-out is one unit of work (one
  `Session`) and traces as one workflow.
- **Kind = net effect.** A coordinator that mutates nothing is an **EVALUATE composite**; one that
  mutates is a `COMMAND`. The mutation boundary holds — it just composes.
- **Purity preserved.** `ctx` *threads through* a coordinator, but pure cores (e.g.
  `evaluate_risk`) still never read `ctx.session`. `pm.advise` operates on the `(Portfolio, IPS)`
  manifest it was *handed* and nest-dispatches only EVALUATE ops — so PM is a **pure advisory
  composite**. The orchestrator owns the surrounding `QUERY` (`ledger.positions`) and `COMMAND`s
  (`optimizer.persist`, `approval.*`, `orders.stage`). Advisory in, acting out — never inside PM.

## 5. Request catalog (grounded in current code)

Each plane registers handlers; the `op` namespace is `plane.verb`.

| `op` | kind | plane | payload → result | backed by |
| --- | --- | --- | --- | --- |
| `ledger.positions` | QUERY | data | `{household_id}` → `list[LotPositionView]` | `list_lot_positions` |
| `risk.evaluate` | EVALUATE | research | `RiskEvaluatePayload{request, manifest}` → `RiskResult` | `evaluate_risk` |
| `policy.check` | EVALUATE | decision | `{positions, ips}` → `IpsDriftReport` | `build_ips_drift_report` |
| `optimizer.propose` | EVALUATE | decision | `{positions, ips}` → `OptimizationResult` | `run_tax_aware_optimizer` |
| `trade.validate` | EVALUATE | decision | `{lot, ips}` → `tuple[bool, list[str]]` | `evaluate_lot_sell_allowed` |
| `tax.scenario` | EVALUATE | decision | `{positions, ips, overlays}` → `TaxScenarioResult` | `run_tax_scenario` |
| `attribution.evaluate` | EVALUATE | decision | `AttributionEvaluatePayload{household_id, positions, as_of_date}` → `AttributionReport` | `evaluate_attribution` (analyst — pa0) |
| `pm.advise` | EVALUATE *(composite)* | decision | `{portfolio, ips, request}` → `AdviceBundle` | nest-dispatches `risk.evaluate` / `attribution.evaluate` / `optimizer.propose` / `tax.scenario` / `policy.check` (§4.1) |
| `report.build` | COMMAND | reporting | `ReportBuildPayload{household_id, period_label?, as_of_date?}` → `WrittenHouseholdReport` | **shipped** — writes `internal.md`/`external.md`/`bundle.json` + audit row; gated on IPS/positions (see `report_writer_implementation.md`) |
| `ingest.run` | COMMAND | data | `{household_id, custodian, file}` → `IngestSummary` | `run_custodian_ingest` |
| `ledger.reconcile` | COMMAND | execution | `{household_id, ingest_run_id}` → `ReconcileResult` | `reconcile_ingest` |
| `optimizer.persist` | COMMAND | decision | `{result, snapshot_id}` → `OptimizationRunView` | `persist_optimization` |
| `approval.create` | COMMAND | decision | `{optimization_run_id, household_id}` → `ApprovalView` | `create_approval_request` |
| `approval.decide` | COMMAND | decision | `{request_id, status, reviewer}` → `ApprovalView` | `update_approval_status` *(decoupled — see below)* |
| `orders.stage` | COMMAND | execution | `{approval_request_id}` → `list[StagedOrderView]` | `stage_orders_from_approval` |
| `ingest.completed` | EVENT | data | `{household_id, run_id, rows}` | — |
| `break.opened` | EVENT | execution | `{household_id, break_id}` | — |
| `order.filled` | EVENT | execution | `{household_id, order_id}` | — |

**`RiskEvaluatePayload`** carries the caller-owned manifest on the wire (matches
`risk_api_contract.md` — the handler does *not* resolve the manifest, which would blur `QUERY` vs
`EVALUATE`):

```python
class RiskEvaluatePayload(BaseModel):
    request: RiskRequest
    manifest: AssetPortfolio
```

**Gate, encoded in the kind.** `orders.stage` is a `COMMAND` whose precondition is an `APPROVED`
approval; the handler **raises** if unmet (the OMS fix). No precondition metadata/DSL — the raise
*is* the declaration.

**Decoupling decision (committed).** Today `update_approval_status` *calls*
`stage_orders_from_approval` when status is `APPROVED` — fusing two COMMANDs (violates S2 and the
taxonomy). **We decouple:** `approval.decide` records the decision only; the orchestrator chains
`approval.decide → orders.stage` by `correlation_id`. Migration §9 removes the internal call. This
is the adaptable shape — staging venue/batching/deferral can vary without touching approval.
(`run_and_persist_optimizer` similarly fuses QUERY+EVALUATE+COMMAND; keep it as a convenience
composite, but expose `ledger.positions` / `optimizer.propose` / `optimizer.persist` as atomic
ops so callers pick granularity.)

**Natural idempotency (per-op, v0 — no store).** `approval.decide` rejects non-`PENDING`;
`orders.stage` returns existing orders for the approval. Both are naturally idempotent. `ingest.run`
and `optimizer.persist` are **not** (a repeat creates a duplicate run) — flagged here; the
`idempotency_key` field is reserved for when Phase-5 retries make duplicates possible.

**The `(Portfolio, IPS)` manifest is the caller's working artifact, sliced per op.** The
diagram's `P,IPS` file is the orchestrator/PM working set (the co-generated pair from
`synthetic_ips.md`); each op receives only the slice it needs — `risk.evaluate` gets the
**portfolio only** (risk is policy-agnostic, per `risk_api_contract.md`); `optimizer.propose` /
`tax.scenario` / `policy.check` get **portfolio + IPS**. Do not push IPS into the risk handler.

**PORTFOLIO ANALYST maps to `policy.check`** (IPS drift / concentration) — no new op; adding a
redundant `portfolio.analyst` would violate S1. A richer analyst bundle, if ever needed, is a
coordinator like `pm.advise`, not a new atomic op.

## 6. Why this shape — the PM lens

The taxonomy is the Portfolio Manager's decision loop, not a generic CRUD set:

- **"The portfolio is the unit of account"** → every `EVALUATE` takes the *whole* book (the risk
  contract takes a full `AssetPortfolio`, never one position). Marginal-contribution analysis is
  the default request, single-name lookups the exception.
- **"Control exposure, not outcomes"** → the mutation boundary *is* the controllable boundary.
  `COMMAND` (size, stage, limit — controllable) is gated; `QUERY`/`EVALUATE` (observe —
  uncontrollable) are free.
- **"Rebalance on calibrated evidence"** → the loop is the rebalance cycle, one `op` per step,
  chained by `correlation_id`:
  `ledger.positions → risk.evaluate → optimizer.propose → optimizer.persist → approval.create →
  approval.decide → orders.stage → order.filled`. The advisory middle (`risk.evaluate →
  optimizer.propose → tax.scenario → policy.check`) is exactly what the **Portfolio Manager**
  (`pm.advise`) coordinates as a pure composite (§4.1); the orchestrator wraps it with the
  `QUERY` and `COMMAND` steps.
- **"Survive to compound"** → `COMMAND` gating + audit is ruin-insurance at the protocol level: no
  un-approved or un-logged mutation. (Idempotency joins this list in Phase 5 — *sized to the
  actual risk*, which today is zero duplicates.)

## 7. Simplicity scorecard

| Axiom | How it's met |
| --- | --- |
| S1 Parsimony | 4 kinds, 6-field envelope (+1 reserved seam), 1 dispatch function — ~80% of the broker spec dropped |
| S2 Singular functionality | one `kind` per message, one handler per `op`; approval/staging decoupled |
| S3 Isolation | planes register handlers; callers know `op`, not implementations; event failures don't cross back |
| S4 Transparency of flow | synchronous request→result; `correlation_id` makes the workflow chain visible end-to-end |
| S5 Universality | payload validated against its registered type at the boundary; same handling for CLI, dashboard, orchestrator, tests |
| S6 Low activation energy | `dispatch_message(ctx, msg)` is one call — no broker to stand up |
| S7 Immediate error recognition | errors raise (with `add_note` context); no DLQ to hide them; the exception is the signal |
| S8 Effortless replication | typed models + a dict + a function — no special infra knowledge |

**Adaptability — reserved vs deferred.** Seams kept now (cheap): typed registry, `DispatchContext`,
`correlation_id`, `idempotency_key` field, `PROTOCOL_VERSION` constant (→ envelope field at Phase 5).
Machinery deferred until needed: idempotency store, retries/at-least-once, broker/pub-sub,
precondition DSL, error envelopes.

## 8. Non-goals (v0)

No broker, queue, or persistence; no delivery guarantees / retries / DLQ; no circuit breakers or
backpressure; no pub-sub infrastructure beyond in-process synchronous fan-out; **no idempotency
store** (field reserved only); **no precondition metadata/DSL** (handlers raise); no
auth/encryption (single process, single tenant). All of these are the `messaging_systems.md`
superset and move to **Phase 5 only if/when a plane goes out-of-process** — the same trigger as
Postgres/Redis.

## 9. Migration (additive — nothing rewritten except the decouple)

1. Add `Message` + `Kind` + `DispatchContext` + `dispatch_message`/`emit_event` + typed `REGISTRY`
   in `warehouse.messaging`; mark `Message`/`Kind`/`DispatchContext` `frozen=True` and register in
   `FROZEN_TYPES`.
2. Register existing plane functions as `(ctx, payload)` wrappers (table §5) — thin, no logic moved;
   the `risk.evaluate` wrapper ignores `ctx` and calls the pure `evaluate_risk`.
3. **Decouple** `update_approval_status`: remove its internal `stage_orders_from_approval` call;
   the orchestrator chains `approval.decide → orders.stage` by `correlation_id`. Update phase-4
   tests accordingly.
   > ⚠ **BEHAVIOR CHANGE — the only step that touches working code + tests (all others are
   > additive).** Removing the call means approving no longer auto-stages. `test_phase4.py::`
   > `test_approval_stages_orders` currently asserts approve ⇒ staged and **will fail** until it
   > chains `orders.stage` explicitly; `test_oms_gate_blocks_unapproved_staging` should still pass.
   > Land the decouple and the test update in the same commit so the gate is never briefly bypassed.
4. First client: `workflows/daily_refresh.py` routes `ingest.run` + `ledger.reconcile` through
   `dispatch_message` and emits `ingest.completed` on success.
5. Wire `emit_event` subscribers to a real dashboard exception/notification panel (phase-2
   exception-queue data source) — a **dashboard deliverable** per the dashboard-first rule (no such
   in-process queue exists today; `infra.notify` is outbound webhooks).
6. Register in `dev_contract_registry.md` §2 with falsifier tests: unknown `op` raises; payload
   type mismatch raises; `orders.stage` on a non-`APPROVED` approval raises; an event subscriber
   failure is visible on the dashboard, not propagated.

---

## 10. Decisions closed (2026-06-28)

Resolves the prior review (Simplicity + PM + adaptability arbitration). Each open item → ruling.

| # | Item | Decision |
| --- | --- | --- |
| 1 | Session/unit-of-work | **Add `DispatchContext`**; uniform `(ctx, payload)` handlers; **EVALUATE handlers ignore `ctx`** so the risk core stays pure (§4). |
| 2 | Envelope vs "six fields" | **Reconciled** — 6 core fields + `message_id` (stamped) + reserved `idempotency_key`; `PROTOCOL_VERSION` is a module constant (§3). |
| 3 | Per-`op` typing | **Registry triples `(payload_type, handler, kind)`**; payload validated at the boundary (§4). |
| 4 | `risk.evaluate` manifest | **`RiskEvaluatePayload{request, manifest}`** on the wire; handler does not resolve manifest (§5). |
| 5 | COMMAND idempotency | **Reserve the field, defer the store** — no duplicates arise in-process (no retries); natural idempotency documented per-op (§2, §5, §8). |
| 6 | EVENT subscriber failures | **Honest** — no queue exists yet; named as a dashboard deliverable (§4, §9.5). |
| 7 | Naming collision | **`dispatch_message` / `emit_event`** (§4). |
| 8 | Immutability | `Message`/`Kind`/`DispatchContext` **frozen + registered** (§9.1). |
| 9 | Catalog errors | **Fixed** — `ledger.positions`→`list[LotPositionView]`, `trade.validate`→`tuple[bool, list[str]]`; added `optimizer.persist`, `approval.create`; `report.build` marked planned (§5). |
| 10 | approval ↔ staging coupling | **Decouple** (committed) — `approval.decide` records only; orchestrator chains `orders.stage` by `correlation_id` (§5, §9.3). |
| 11 | Precondition "declaration" | **No metadata/DSL** — the handler raising *is* the declaration; prose reworded (§5, §8). |
| 12 | `repo_structure.pdf` two-tier hierarchy | **Reconciled, no structural change** — declared **nested dispatch** + `pm.advise` pure composite coordinator (§4.1); added **`tax.scenario`**; mapped **PORTFOLIO ANALYST → `policy.check`** (no redundant op); `(P,IPS)` is the caller's sliced working artifact, risk stays policy-agnostic (§5). The 4 kinds and the envelope are unchanged. |

**Ship gate:** mark **shipped** once §9 lands and `daily_refresh` (or a rebalance smoke) routes
through `dispatch_message` end-to-end, with the §9.6 falsifier tests green.
