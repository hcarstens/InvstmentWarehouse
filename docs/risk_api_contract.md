# Risk API Contract — Simplification Design

**Status:** proposed (design only — no code yet)
**Author:** design pass with Claude, 2026-06-26
**Owner:** risk API
**Related:** `docs/research/risk_units_measures.md`, `docs/research/portfolio_risk.md`,
`docs/research/simple_risk_models.md`, `docs/code_review_claude_2026-06-26.md`

---

## 1. Goal

Collapse the risk workflow to a single, pure contract:

```
orchestrator → risk_api{ request, manifest } → { report, deltas }
```

- **Orchestrator** owns *where portfolios come from* (ledger or synthetic) and *what to do
  with the answer* (arbitration — acting on deltas is out of scope for risk).
- **Risk API** owns *one thing*: given a portfolio manifest and a request, compute the risk
  report and — if the request describes a change — the deltas that change implies.

The current Level 1–4 engine internals (`evaluate_portfolio_risk`) stay intact. This redesign
is about the **edges**, not the math.

## 2. Why the current workflow is complex

| Problem | Where | Effect |
| --- | --- | --- |
| Three ways in, no single contract | dict `evaluate_risk_request` ([api.py](../src/warehouse/research/risk/api.py)), object `evaluate_portfolio_risk` ([engine.py](../src/warehouse/research/risk/engine.py)), ledger `build_portfolio_from_holdings` ([portfolio_builder.py](../src/warehouse/research/risk/portfolio_builder.py)) | Manifest is implicit, split across `AssetPortfolio` + `horizon` + `notional_usd`; callers wire it differently |
| God-orchestrator | [`load_risk_dashboard`](../src/warehouse/dashboard/risk_data.py) | Bootstraps DB, loads another dashboard for side effects, reads ledger, builds portfolio, evaluates risk, **and swallows all errors** (review finding #5) |
| No deltas | — | Output is a single report; no "how does risk change under this proposal?" |

## 3. The contract

One entry point. Pure. No DB, no bootstrap, no swallowed errors — it **raises** and the
orchestrator decides presentation.

```python
def evaluate_risk(request: RiskRequest, manifest: PortfolioManifest) -> RiskResult: ...
```

### 3.1 Types

```python
class PortfolioManifest(BaseModel):       # WHAT you hold — the unit of synthetic data
    manifest_id: str
    allocations: list[AllocationSlot]     # existing slot shape, inlined (replaces AssetPortfolio)
    source: str = "synthetic"             # provenance: synthetic | ledger | scenario
    complexity: int | None = None         # 0..N rung on the synthetic ladder (synthetic only)

class RiskRequest(BaseModel):             # the QUESTION asked of the manifest
    horizon: RiskHorizon
    notional_usd: Decimal | None = None   # evaluate at this dollar size (enables $VaR/$ES, $P&L)
    confidence: Decimal | None = None     # α override; defaults to settings
    overlay: ManifestOverlay | None = None  # the proposed change/scenario → drives deltas

class RiskResult(BaseModel):              # frozen — register in FROZEN_TYPES
    report: PortfolioRiskReport           # risk of the manifest as-is (the baseline)
    deltas: RiskDeltas | None = None      # None unless request.overlay is set
```

**Decision — horizon/notional live in the request, not the manifest.** A manifest is *what you
hold* (a shape); horizon and notional are *how you're asking about it*. This lets the same
synthetic shape be evaluated at different horizons/notionals without cloning manifests.

### 3.2 The delta model (single manifest in)

The orchestrator sends **one** manifest — the current portfolio. The **request** carries the
proposed change as an `overlay`. The risk API does the rest:

```
report  = evaluate(manifest, request)                      # baseline
if request.overlay:
    derived = apply_overlay(manifest, request.overlay)     # risk derives the proposed manifest
    proposed = evaluate(derived, request)
    deltas  = diff(report, proposed)                        # baseline → proposed
return RiskResult(report, deltas)
```

The orchestrator never constructs the proposed portfolio — it expresses *intent*; risk owns
*computation*. The orchestrator then **arbitrates** (act / don't act / route for approval) —
explicitly out of scope for the risk API. This keeps risk advisory-only, consistent with
"decision support, not autonomous alpha."

```python
class ManifestOverlay(BaseModel):
    """A declarative, compact perturbation — NOT a second full manifest."""
    weight_tilts: dict[AssetClass, Decimal] = {}   # e.g. {equity: -0.10, fixed_income: +0.10}
    add_sleeves: list[AllocationSlot] = []          # new exposures
    drop_sleeves: list[AssetClass] = []             # exited exposures
    stress_pack: str | None = None                  # named replay (reuses Level 4 vocab)
    label: str | None = None                        # "rebalance to 60/40", "redomicile overlay"
    # apply_overlay re-normalizes weights to sum to 1 and re-validates the manifest

class MetricDelta(BaseModel):
    metric: str                  # "annualized_volatility" | "parametric_var" | "parametric_es" | "dollar_var"
    baseline: Decimal
    proposed: Decimal
    delta: Decimal               # proposed − baseline
    pct_change: Decimal | None

class RiskDeltas(BaseModel):     # frozen — register in FROZEN_TYPES
    overlay_label: str | None
    baseline_fingerprint: str    # both fingerprints travel for audit replay
    proposed_fingerprint: str
    headline: list[MetricDelta]               # Level 1 metrics
    by_class_variance_delta: dict[str, Decimal]  # Level 2 contribution shift
```

**Overlay vocabulary is the one design knob that grows over time.** v0 = `weight_tilts` +
`add/drop_sleeves` + `stress_pack` covers rebalance and named-stress what-ifs. Tax-vector /
redomicile overlays (per `tax_arbitrage.md`) are a later extension that changes the *rate
vector*, not the allocation shape — they slot in as a new overlay field without touching the
contract.

## 4. Synthetic manifests — a complexity ladder

`synthetic.py` returns `PortfolioManifest`s at increasing complexity. This is the test/demo
spine and what satisfies the "simple → complex" requirement. Each rung lights up one more level
of the unit hierarchy, so a failing rung localizes the break.

```python
def rung(level: int) -> PortfolioManifest: ...
```

| Rung | Shape | Exercises |
| --- | --- | --- |
| 0 | single equity sleeve (β=1) | Level 1 σ/VaR smoke test |
| 1 | 60/40 equity + fixed income | duration bucket, 2×2 covariance |
| 2 | + commodities + FX | multi-asset aggregation, native sensitivity units |
| 3 | + illiquid alternatives (tier 3) | liquidity-time units, fermi sleeves |
| 4 | + concentrated weights, fermi-tagged | measurement modes, tail behavior, confidence band |

Deltas are tested by sending `rung(n)` as the manifest with an `overlay` that morphs it toward
`rung(n+1)`'s shape.

## 5. How the orchestrator collapses

```python
# before: ~40-line load_risk_dashboard doing 6 jobs + swallowing errors
manifest = build_household_manifest(household_id)            # OR synthetic.rung(3)
result   = evaluate_risk(RiskRequest(horizon=..., notional_usd=..., overlay=proposed), manifest)
present(result)                                              # dashboard/persist; errors propagate
```

- `build_portfolio_from_holdings` → `build_household_manifest(household_id) -> PortfolioManifest`
  tagged `source="ledger"`. DB/bootstrap logic leaves the risk path entirely.
- The dict HTTP path (`evaluate_risk_request`) becomes a thin adapter: parse JSON →
  `RiskRequest` + `PortfolioManifest` → `evaluate_risk` → `model_dump`. One code path underneath.
- The error swallow in `load_risk_dashboard` disappears: the pure function raises, the
  presentation layer chooses how to show failure (fixes review finding #5).

## 6. Convergence — three paths → one

```
            ┌─ build_household_manifest (ledger)  ─┐
manifests ──┤─ synthetic.rung(n)                  ─┼─► evaluate_risk(request, manifest) ─► {report, deltas}
            └─ JSON adapter (HTTP)                 ─┘
```

Ledger, synthetic, and HTTP all produce a `PortfolioManifest` and call the same
`evaluate_risk`. No capability lives in only one path.

## 7. Migration plan (engine internals untouched)

1. **Add types** — `PortfolioManifest`, `RiskRequest`, `RiskResult`, `RiskDeltas`,
   `ManifestOverlay`, `MetricDelta` (new `models_io.py` alongside `models.py`).
2. **Add `evaluate_risk` service** (`service.py`) wrapping the existing
   `evaluate_portfolio_risk`; implement `apply_overlay` + `diff`. No engine changes.
3. **Synthetic ladder** (`synthetic.py`) `rung(0..4)`.
4. **Refactor builder** — `build_household_manifest` returns a `PortfolioManifest`.
5. **Collapse orchestrator** — `load_risk_dashboard` → manifest + `evaluate_risk` + present;
   remove the bare-`except` swallow.
6. **Adapter** — re-point `evaluate_risk_request`/`evaluate_risk_json` at `evaluate_risk`;
   keep the JSON wire shape backward-compatible (accept legacy `{asset_portfolio, horizon}`).
7. **Freeze + register** — `RiskResult`, `RiskDeltas`, and the report snapshots in
   `FROZEN_TYPES` (closes review medium item on unfrozen risk snapshots).
8. **Tests** — synthetic ladder evaluates clean per rung; overlay/delta correctness
   (tilt equity down ⇒ vol/VaR delta negative); adapter back-compat; frozen registry.
9. **Dashboard** — a deltas panel (baseline → proposed headline metrics) per the
   dashboard-first rule.

## 8. Boundaries & conventions

- **Pure & deterministic.** `evaluate_risk` has no I/O; identical (request, manifest) →
  identical result. Fingerprints on both base and proposed make deltas audit-replayable.
- **Errors bubble.** The service raises typed errors; only the orchestrator/adapter maps them
  to dashboard state or HTTP codes.
- **Advisory only.** Risk computes what-would-happen; it never persists trades, decides, or
  executes. Arbitration is the orchestrator's, behind human approval gates.
- **Frozen results.** `RiskResult`/`RiskDeltas` are immutable snapshots, registered for the
  `test_frozen.py` check.

## 9. Open decisions (for the owner)

1. **Overlay v0 vocabulary** — is `weight_tilts + add/drop_sleeves + stress_pack` enough for
   the first orchestrator use cases, or is a tax-rate-vector overlay needed in v0?
2. **Multiple overlays per request** — single `overlay` (one what-if) vs `list[overlay]`
   (compare N proposals in one call, returning `list[RiskDeltas]`).
3. **Headline metric set** — which Level 1 metrics are first-class in `RiskDeltas.headline`
   (proposed: ann_vol, parametric_var, parametric_es, dollar_var when notional present).
4. **Adapter back-compat window** — keep the legacy `{asset_portfolio, horizon}` JSON shape
   indefinitely, or deprecate once the orchestrator moves to manifests.
```
