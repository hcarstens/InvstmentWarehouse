# Risk API Contract — Simplification Design

**Status:** v0 proposed (engine exists; new contract not built)
**Owner:** risk API
**Related:** `docs/research/risk_units_measures.md`, `docs/research/portfolio_risk.md`,
`docs/research/simple_risk_models.md`, `docs/code_review_claude_2026-06-26.md`

> **North star:** the risk plane becomes a **standalone module** with one pure entry point,
> plugged into the larger workflow over an API. The project hands it a portfolio + a question;
> it returns a report. It owns no DB, no decisions, no execution.

---

## 1. Goal

Collapse three entry paths into one pure contract:

```
caller ──► evaluate_risk(request, manifest) ──► RiskResult{ report, deltas }
              ▲                                        │
   ledger adapter │ synthetic.rung(n) │ HTTP POST /api/risk
```

- **Caller** owns *where portfolios come from* and *what to do with the answer* (arbitration —
  out of scope for risk).
- **Risk module** owns *one thing*: given a manifest + request, compute the report. The
  `deltas` slot is reserved (see [v1](#v1--overlays--deltas)) so the response shape never changes.

Engine internals (`evaluate_portfolio_risk`, Levels 1–4) stay intact. This is about the
**edges**, not the math.

## 2. Why the current workflow is complex

- **Three ways in, no single contract** — dict [`evaluate_risk_request`](../src/warehouse/research/risk/api.py), object [`evaluate_portfolio_risk`](../src/warehouse/research/risk/engine.py), ledger [`build_portfolio_from_holdings`](../src/warehouse/research/risk/portfolio_builder.py). The "manifest" is implicit, split across `AssetPortfolio` + `horizon` + `notional_usd`.
- **God-orchestrator** — [`load_risk_dashboard`](../src/warehouse/dashboard/risk_data.py) bootstraps the DB, loads another dashboard for side effects, reads the ledger, builds the portfolio, evaluates risk, **and swallows all errors** (`except Exception`, still live — review finding #5).
- **No `{report, deltas}` shape** — output is a bare report; nothing reserved for "how does risk change under a proposal?"

## 3. The v0 contract

One entry point. Pure. No DB, no bootstrap, no swallowed errors — it **raises**; the caller
presents.

```python
def evaluate_risk(request: RiskRequest, manifest: AssetPortfolio) -> RiskResult: ...
```

### 3.1 Types — reuse `AssetPortfolio`, add an envelope

No new `PortfolioManifest` type (it was a near-duplicate of `AssetPortfolio`). Add two optional
provenance fields instead, and wrap the output so `deltas` has a home from day one.

```python
class AssetPortfolio(BaseModel):          # the manifest — WHAT you hold
    portfolio_id: str | None = None
    allocations: list[AllocationSlot]     # unchanged; weights sum to 1
    source: str = "synthetic"             # + provenance: synthetic | ledger
    complexity: int | None = None         # + synthetic rung tag (synthetic only)

class RiskRequest(BaseModel):             # the QUESTION asked of the manifest
    horizon: RiskHorizon
    notional_usd: Decimal | None = None   # evaluate at this $ size → $VaR/$ES/$P&L
    run_scenarios: ScenarioSet = ScenarioSet.NONE   # none | high_risk | low_risk | all
    # overlay: ManifestOverlay | None = None         # v1 — envelope already supports it

class RiskResult(BaseModel):              # frozen + registered in FROZEN_TYPES (v0)
    report: PortfolioRiskReport           # base / house-view risk of the manifest
    scenarios: dict[str, PortfolioRiskReport] = {}  # alt regimes per run_scenarios (risk-owned)
    deltas: RiskDeltas | None = None      # null in v0; no signature change when v1 lands
```

**Decision — horizon/notional live in the request, not the manifest.** A manifest is *what you
hold*; horizon/notional are *how you're asking*. One synthetic shape, many questions, no cloning.

**Decision — keep the `RiskResult` envelope even though `deltas` is always null in v0.** Returning
a bare `PortfolioRiskReport` would make deltas a breaking return-type change later. The envelope
is the whole point of a stable base.

### 3.2 Risk assumptions — owned by risk, selected by a flag

Model assumptions (vol/return priors, correlations, tail multipliers, stress shocks) are **risk
internals, not a caller input**. The caller never constructs an assumption set — it picks which
regimes to run via `request.run_scenarios`. Risk owns a named, version-pinned, PSD-validated
catalog:

```python
class ScenarioSet(StrEnum):           # the caller's whole surface for assumptions
    NONE = "none"                     # base / house-view only
    HIGH_RISK = "high_risk"           # base + crisis regime
    LOW_RISK = "low_risk"             # base + benign regime
    ALL = "all"

# warehouse/research/risk/scenarios.py — INTERNAL, version-pinned, PSD-validated
def assumptions_for(name: str) -> RiskAssumptions: ...   # base | high_risk | low_risk
```

- **Why risk-owned, not caller-injected** — an injected correlation matrix can be non-PSD
  (negative portfolio variance); an owned catalog validates PSD at load, so that failure class is
  impossible. It also keeps the integration surface an enum, not a domain object — the plug-and-play
  boundary.
- **Regime ≠ stress replay** — `high_risk`/`low_risk` swap the *assumption set* and re-run all of
  Levels 1–4 (`high_risk`: correlations → ~+0.85, vols ×~1.4, fatter ES). Distinct from the Level 4
  *named stress replay* (2008/2020/2022), which applies a fixed return shock to positions inside one
  report.
- **Audit** — the selected regime + `risk_model_version` fold into the report fingerprint
  (`high_risk @ 2026.02`), so every scenario report is reproducible.
- **Upstream assumption changes** happen in this one owned catalog; callers running `all` pick them
  up automatically.
- **`scenarios` map + deltas** — `run_scenarios` can return several reports, so `RiskResult.scenarios`
  holds the alternates. `diff(report, scenarios["high_risk"])` is itself a delta — the **same diff
  machinery** serves both assumption-regime deltas (here) and v1 portfolio-overlay deltas.

Arbitrary caller-supplied assumptions (research sweeps, bespoke client CMAs) are an explicit escape
hatch deferred to [v1](#v1--overlays--deltas) — the primary path stays the flag.

| Caller sets | Risk owns |
| --- | --- |
| `run_scenarios` enum | `scenarios.py` catalog + PSD validation |
| `horizon`, `notional_usd` | Engine, Levels 1–4 |
| `manifest` (`AssetPortfolio`) | Fingerprint, `PortfolioRiskReport` |

**Regime vs existing `stress.py`.** `high_risk` / `low_risk` swap the *covariance / vol priors*
and re-run the full engine — a second pass with a different assumption set. Level 4 *named stress
replay* (2008/2020/2022) stays in [`stress.py`](../src/warehouse/research/risk/stress.py): a fixed
return shock *inside one report*, not a separate scenario map entry. Do not duplicate that path when
building `scenarios.py`.

## 4. Module boundary — plug-and-play

The risk module is importable and runnable with **zero project state**. Its public surface is its
package `__init__`:

```python
# warehouse/research/risk/__init__.py — the integration surface
from .service   import evaluate_risk
from .models    import AssetPortfolio, AllocationSlot, RiskHorizon, RiskRequest, RiskResult
from .synthetic import rung
```

- **Pure core** (`service`, `engine`, `models`, `covariance`, `var_es`, …) imports only stdlib,
  pydantic, numpy/scipy, and its own version-pinned `assumptions.py` / `scenarios.py`. **No
  `warehouse.data` / `warehouse.infra` imports.** v0 lifts the pinned constants (α, windows,
  correlations, stress shocks) into a frozen `RiskAssumptions` catalog so the core runs without
  project config; the legacy `get_settings()` reads collapse into the catalog defaults.
- **Integration surfaces** (all thin, all over the same `evaluate_risk`):
  1. **Function** — `evaluate_risk(request, manifest)` for in-process callers.
  2. **HTTP** — `POST /api/risk`: JSON → `RiskRequest` + `AssetPortfolio` → `evaluate_risk` →
     `model_dump`. `GET /api/risk` stays the schema (`risk_api_schema`). One handler, two verbs —
     not a second route. *(Shipped today as `evaluate_risk_request`; migration re-points it at
     `evaluate_risk` and extends the schema with `run_scenarios`.)*
  3. **Ledger adapter** — `build_household_manifest(household_id) -> AssetPortfolio` (tagged
     `source="ledger"`) lives at the **edge**, not in the pure core, so the coupling to the
     ledger stays out of the risk math.
- **Standalone test path** — `synthetic.rung(n)` produces manifests with no DB, so the whole API
  is exercisable in isolation.

## 5. Synthetic manifests — the ground-truth corpus (v0: rungs 0–2)

`synthetic.py` is the **canonical ground truth the module builds on and iterates over** — a no-DB
corpus of `AssetPortfolio`s at increasing complexity. Every layer (engine, scenario catalog, later
overlays/deltas) is developed and regressed against it, so a failing rung localizes the break
before any ledger is involved.

| Rung | Shape | Exercises |
| --- | --- | --- |
| 0 | single equity sleeve (β=1) | Level 1 σ/VaR smoke test |
| 1 | 60/40 equity + fixed income | duration bucket, 2×2 covariance |
| 2 | + commodities + FX | multi-asset aggregation, native sensitivity units |

The regression surface is the **matrix `rung × run_scenarios`** — each cell carries pinned golden
values, composed by a test fixture (**not** a wire type):

```python
class Scenario(BaseModel):       # tests only — NOT exported from risk/__init__.py
    portfolio: AssetPortfolio    # synthetic.rung(n)
    request: RiskRequest         # horizon, notional, run_scenarios
    expected: dict | None = None # golden Level-1 values for regression
```

This `Scenario` fixture is where the "manifest" ergonomics live — composing a rung with a request
in the test layer, never bundled into the wire contract (which would force cloning the portfolio
per regime). Rungs 3–4 (illiquid alts, fermi-tagged / concentrated) land in
[v1](#v1--overlays--deltas).

## 6. Boundaries & conventions

- **Pure & deterministic** — no I/O; identical `(request, manifest)` → identical result;
  fingerprinted for audit replay.
- **Errors bubble** — the service raises typed errors; only the caller/adapter maps them to
  dashboard state or HTTP codes.
- **Advisory only** — risk computes what-would-happen; never persists trades, decides, or
  executes. Arbitration is the caller's, behind human approval gates.
- **Frozen results** — `RiskResult` (and the report snapshots) are immutable, registered for
  `test_frozen.py`. (Closes the review's unfrozen-snapshot item.)

## 7. Migration (engine untouched)

Ship in two slices so step 2's size is visible up front.

### v0a — envelope (ship first)

1. Add `RiskRequest` + `RiskResult` + `evaluate_risk(request, manifest)` wrapping
   `evaluate_portfolio_risk`; freeze + register `RiskResult`. `run_scenarios` defaults to `none`;
   `scenarios={}`, `deltas=null`.

### v0b — scenario catalog *(largest v0 chunk)*

2. Lift assumption globals into a frozen `RiskAssumptions` + internal `scenarios.py` catalog
   (`base`/`high_risk`/`low_risk`, PSD-validated); thread it through the engine sub-modules; wire
   `run_scenarios` → `RiskResult.scenarios`; fold regime + `risk_model_version` into the
   fingerprint. Reuse existing [`stress.py`](../src/warehouse/research/risk/stress.py) for Level 4
   named replays — do not reimplement inside `scenarios.py`.

### v0c — integration

3. Add `synthetic.rung(0..2)` + the `rung × run_scenarios` golden corpus (no DB).
4. Add `build_household_manifest`; collapse `load_risk_dashboard` to manifest → `evaluate_risk`
   → present — **narrow the `except`, drop the `load_phase2_dashboard` side effect**.
5. Point `POST /api/risk` at `evaluate_risk`; extend `GET /api/risk` schema with `run_scenarios`;
   keep legacy `{asset_portfolio, horizon}` JSON accepted on POST.

## 8. Decisions (closed)

| Question | v0 default |
| --- | --- |
| New `PortfolioManifest` type? | **No** — reuse `AssetPortfolio` + `source`/`complexity` |
| Drop the `RiskResult` envelope? | **No** — keep it; `deltas=null` in v0 (non-breaking) |
| Frozen results in v0? | **Yes** — convention-mandated, one line |
| Synthetic ladder in v0? | **Rungs 0–2 only** (no-DB test spine); 3–4 → v1 |
| Assumptions: injected or risk-owned? | **Risk-owned** version-pinned, PSD-validated catalog; caller picks via `run_scenarios` |
| `run_scenarios` values | `none` \| `high_risk` \| `low_risk` \| `all` (base always runs) |
| Arbitrary assumption override? | **v1 escape hatch** — research sweeps / bespoke CMAs only |
| Overlay / delta math in v0? | **Defer to v1** — envelope reserved |
| Headline delta metrics (v1) | ann_vol, parametric_var, parametric_es (+ dollar when notional) |
| Multiple overlays per request (v1) | **Single** overlay |
| JSON back-compat | **Keep** `{asset_portfolio, horizon}` |
| HTTP evaluate path | **`POST /api/risk`** (existing); **`GET /api/risk`** = schema. No `/orchestrate` route. |
| Term for the caller | **"caller"** in code; "orchestrator" = the specific project caller |

---

## v1 — overlays & deltas

Deferred from the base contract. The `RiskResult.deltas` slot and `RiskRequest.overlay` field are
already reserved, so v1 adds capability **without changing the signature**.

**Delta model (single manifest in).** The caller sends one manifest (current portfolio); the
request carries the proposed change as an `overlay`; risk applies it, re-evaluates, and diffs.
The caller never builds the proposed portfolio — it states intent; risk owns the math; the caller
arbitrates (out of scope).

```python
baseline = evaluate_risk(request, manifest)           # baseline
if request.overlay:
    derived = apply_overlay(manifest, request.overlay)
    proposed = evaluate_risk(request, derived)
    deltas = diff(baseline.report, proposed.report)
```

```python
class ManifestOverlay(BaseModel):
    """Declarative, compact perturbation — NOT a second full manifest."""
    weight_tilts: dict[AssetClass, Decimal] = {}   # {equity: -0.10, fixed_income: +0.10}
    add_sleeves: list[AllocationSlot] = []
    drop_sleeves: list[AssetClass] = []
    stress_pack: str | None = None                 # named replay (reuses Level 4 vocab)
    label: str | None = None
    # apply_overlay re-normalizes weights to 1 and re-validates

class MetricDelta(BaseModel):
    metric: str                  # "annualized_volatility" | "parametric_var" | ...
    baseline: Decimal
    proposed: Decimal
    delta: Decimal               # proposed − baseline
    pct_change: Decimal | None

class RiskDeltas(BaseModel):     # frozen + registered when introduced
    overlay_label: str | None
    baseline_fingerprint: str    # both fingerprints travel for audit replay
    proposed_fingerprint: str
    headline: list[MetricDelta]                   # Level 1 metrics
    by_class_variance_delta: dict[str, Decimal]   # Level 2 contribution shift
```

**Also in v1:**

- **Synthetic rungs 3–4** — illiquid alternatives (liquidity-time units, tier 3) and
  concentrated / fermi-tagged sleeves (measurement modes, tail/confidence band).
- **Arbitrary `RiskAssumptions` override** — explicit escape hatch (`assumptions=` on
  `evaluate_risk`) for research sweeps and bespoke client CMAs, defaulting to the catalog. The v0
  catalog already lifts the pinned constants out of `get_settings()`; this just exposes them.
- **Deltas dashboard panel** — baseline → proposed headline metrics, per the dashboard-first rule.
- **Tax-vector / redomicile overlays** — change the *rate vector*, not the allocation shape
  (`tax_arbitrage.md`); a new overlay field, contract unchanged.

---

## Review / iteration log

| Date | Note |
| --- | --- |
| 2026-06-26 | Initial design (Claude): single contract, manifest-vs-question, overlay/deltas. |
| 2026-06-26 | Cursor review: doc over-specified for a simplification doc; recommended a v0 cut. |
| 2026-06-26 | Arbitration (Claude): accepted Cursor's *reuse `AssetPortfolio`*, *close decisions with defaults*, *one-page structure*; **rejected** dropping the `RiskResult` envelope (breaking change) and deferring frozen results (convention-mandated); kept a minimal synthetic spine (user requirement). Verified the two "orchestration stories" are one path + HTTP face. Result: this v0 + a `## v1` appendix. |
| 2026-06-26 | Assumptions decision (owner + Claude): risk **owns** a version-pinned, PSD-validated scenario catalog (`base`/`high_risk`/`low_risk`); caller selects via a `run_scenarios` flag, not an injected assumptions object. `RiskResult` gains a `scenarios` map; same diff machinery serves regime + overlay deltas. Pulled the catalog + flag into v0; arbitrary override → v1 escape hatch. Reverses the earlier injectable-third-arg idea. |
| 2026-06-26 | Cursor review (post-edit): aligned HTTP to **`POST /api/risk`** (no `/orchestrate`); fixed v1 pseudocode arg order to `(request, manifest)`; split migration into **v0a / v0b / v0c** with v0b flagged as largest chunk; tied regimes to existing `stress.py`; `Scenario` fixture marked test-only. |
