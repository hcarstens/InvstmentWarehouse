# Risk API — Implementation Plan (HNW-informed)

**Status:** v1 shipped (overlays + deltas); HNW compositional generator remains planned
**Date:** 2026-06-26
**Inputs:** [`risk_api_contract.md`](risk_api_contract.md) (design),
[`hnw_portfolios.md`](research/hnw_portfolios.md) (synthetic corpus + axioms),
[`heuristics/Risk Management.md`](heuristics/Risk%20Management.md) (RM1–RM7)

---

## 1. Principle — two layers, one wire shape

HNW research: a portfolio is a **household graph** (entities → accounts → lots), not a weight
vector. The risk contract is still correct for v0 — but **only as Shape A** (sleeve-level
`AssetPortfolio`).

| Layer | Package (planned) | Output | Consumer |
| --- | --- | --- | --- |
| **Risk core** | `warehouse.research.risk` | `RiskResult` | Dashboard, HTTP, tests |
| **HNW generator** | `warehouse.research.synthetic` *(v1)* | Shape B fixture + Shape A projection | Optimizer, recon, risk rung 3+ |

Do **not** put the compositional HNW pipeline (`cohort → graph → lots → alts`) inside the
pure risk module. The generator **projects** to `AssetPortfolio` for `evaluate_risk`; risk never
imports `warehouse.data` / `warehouse.infra`.

```text
                    ┌─ synthetic.rung(0..2)     ─┐  v0 — hand-built sleeves in risk/
Shape A manifest ───┤─ HNW.project_to_manifest()─┼──► evaluate_risk(request, manifest)
                    └─ build_household_manifest()─┘  v0c — ledger edge adapter
```

---

## 2. Rung ladder — who owns what

Aligned with both docs; **v0 ships 0–2 only**.

| Rung | Owner (v0) | Source | HNW cohort / notes |
| --- | --- | --- | --- |
| 0 | `risk/synthetic.py` | Single equity β=1 | Smoke — no cohort |
| 1 | `risk/synthetic.py` | 60/40 | Smoke — no cohort |
| 2 | `risk/synthetic.py` | + commodities + FX | Multi-asset aggregation |
| 3 | `research/synthetic/` *(v1)* | 5-sleeve + liquidity tiers | `general_hnw`, `uhnw_inherited` sleeve priors |
| 4 | `research/synthetic/` *(v1.1)* | Lots + concentration + alts calls | `founder_executive`, `concentrated_stress` |

**v0 rule:** `synthetic.rung(n)` for `n in {0,1,2}` lives in the risk package and needs **no**
cohort engine. Rungs 3–4 are **blocked on** the HNW compositional generator, not on
`evaluate_risk`.

---

## 3. Migration slices (contract §7) — tasks + acceptance

Apply **SDG3** from HNW research: validate by **downstream tasks** (risk regression, optimizer
smoke, recon), not weight realism.

### v0a — envelope *(~1 PR)*

**Goal:** one pure entry point; engine unchanged.

| Task | File(s) |
| --- | --- |
| Add `RiskRequest`, `RiskResult`, `ScenarioSet` | `risk/models.py` |
| Add `source`, `complexity` on `AssetPortfolio` | `risk/models.py` |
| `evaluate_risk(request, manifest) -> RiskResult` | `risk/service.py` *(new)* |
| Freeze + register `RiskResult` | `integrity/frozen_registry.py`, `tests/test_frozen.py` |
| Export public surface | `risk/__init__.py` |

**Acceptance:**

- `evaluate_risk(RiskRequest(horizon=5y), rung(1))` returns `RiskResult` with `report` matching
  today's `evaluate_portfolio_risk` for the same inputs.
- `scenarios={}`, `deltas=null`, `run_scenarios=none`.
- `pytest tests/test_frozen.py` passes.
- No new imports of `warehouse.data` / `warehouse.infra` in `risk/service.py`.

### v0b — scenario catalog *(largest chunk — ~2 PRs)*

**Goal:** `run_scenarios` flag; risk-owned assumptions; RM5/RM6 tail + correlation discipline.

| Task | File(s) |
| --- | --- |
| Frozen `RiskAssumptions` dataclass | `risk/assumptions.py` refactor |
| `scenarios.py`: `base`, `high_risk`, `low_risk` + PSD check at load | `risk/scenarios.py` *(new)* |
| Thread assumptions into engine (replace scattered `get_settings()` in math path) | `engine.py`, `covariance.py`, … |
| `run_scenarios` → `RiskResult.scenarios` | `service.py` |
| Regime suffix in fingerprint | `fingerprint.py` |
| Level 4 named stress **unchanged** | `stress.py` — no duplication |

**HNW-informed acceptance:**

- `high_risk` raises portfolio vol vs `base` on rung 1 (RM5 — tail attention).
- Correlation matrix PSD-validated at import (RM6 — crisis coupling via catalog, not injection).
- `run_scenarios=all` returns 3 reports; fingerprints differ and include regime tag.
- Golden cells: `rung(0..2) × {none, high_risk}` pinned in `tests/fixtures/risk_golden/`.

**Defer:** cohort-conditioned assumption sets — use global `high_risk`/`low_risk` until rung 3.

### v0c — integration *(~2 PRs)*

**Goal:** callers use `evaluate_risk`; dashboard stops being a god-module.

| Task | File(s) |
| --- | --- |
| `synthetic.rung(0..2)` | `risk/synthetic.py` *(new)* |
| `Scenario` test fixture + golden matrix | `tests/test_risk_synthetic.py` |
| `build_household_manifest(hh_id)` at edge | `risk/adapters/ledger.py` *(new)* — wraps `portfolio_builder` |
| Slim `load_risk_dashboard` | `dashboard/risk_data.py` — `_ensure_demo_refresh`, narrow `except` |
| HTTP → `evaluate_risk` | `risk/api.py`, `dashboard/server.py` |
| Extend `GET /api/risk` schema | `risk/api.py` `risk_api_schema()` |

**HNW-informed acceptance (SDG3):**

- `POST /api/risk` with `synthetic.rung(2)` JSON → same report as in-process call.
- `build_household_manifest(DEMO_HOUSEHOLD_ID)` → `source="ledger"`, weights reconcile to
  household PnL (HNW axiom: Σ lots = NAV).
- Dashboard risk panel loads via manifest → `evaluate_risk` → present; domain errors mapped,
  `KeyError` bubbles.
- Optimizer smoke on demo household still passes (`tests/test_phase3.py`) — no regression.

---

## 4. Provenance fields — v0 minimal, v1 HNW-complete

Contract v0 adds `source` + `complexity`. HNW research adds more — **stage incrementally**.

| Field | v0 | v1 (HNW generator) |
| --- | --- | --- |
| `source` | `synthetic` \| `ledger` | + `scenario_card` |
| `complexity` | rung 0–2 | rung 3–4 |
| `cohort_id` | — | `general_hnw`, `founder_executive`, … |
| `generator_version` | — | semver + `axiom_set_hash` |
| `seed` | — | deterministic replay |
| `tension_tags[]` | — | SDG4 — at least one tension per book |

Fingerprint should hash provenance fields present on the manifest so silent regression (HNW
falsifier: missing `generator_version`) is impossible.

---

## 5. SDG acceptance matrix (risk implementation)

Map HNW SDG axioms to **what we test in v0** vs **what waits for the generator**.

| SDG | Criterion | v0 (risk API) | v1 (HNW generator) |
| --- | --- | --- | --- |
| SDG1 Fidelity | IPS + recon pass | Ledger manifest vs demo seed | Full graph emit |
| SDG2 Counterfactuals | Named negations | `run_scenarios` high/low | `concentrated_stress` cohort |
| SDG3 Falsification | Downstream tasks | Rung × scenario golden + phase3 smoke | + TLH lot tests |
| SDG5 Provenance | Traceable emit | `source`, `complexity`, fingerprint | Full manifest seal |
| SDG7 Composition | Staged pipeline | `synthetic.rung` only | `cohort → graph → lots → …` |

**v0 falsifier to watch:** weight-only rungs 0–2 pass risk but would fail lot-level TLH — **that
is expected**; document in tests that rung ≥3 is required for optimizer fidelity tests (HNW
disconfirming limit).

---

## 6. Module map (target tree)

```text
warehouse/research/risk/
  __init__.py          # evaluate_risk, rung, public types
  service.py           # evaluate_risk — pure orchestration of engine + scenarios
  models.py            # + RiskRequest, RiskResult, ScenarioSet; AssetPortfolio provenance
  scenarios.py         # assumptions_for(), PSD validation
  synthetic.py         # rung(0..2) — NOT the HNW compositional generator
  adapters/
    ledger.py          # build_household_manifest — only infra touchpoint
  engine.py            # evaluate_portfolio_risk (unchanged signature initially)
  api.py               # HTTP adapter → evaluate_risk
  …                    # existing math modules

warehouse/research/synthetic/   # v1 — HNW compositional generator (Shape B)
  cohort.py
  graph.py
  sleeves.py
  manifest.py          # project_to_asset_portfolio() → Shape A for rung 3+
```

---

## 7. Test plan summary

| Suite | Covers |
| --- | --- |
| `tests/test_risk_service.py` | `evaluate_risk` envelope, error propagation |
| `tests/test_risk_scenarios.py` | `run_scenarios`, PSD, fingerprint regime suffix |
| `tests/test_risk_synthetic.py` | `rung(0..2)`, golden matrix |
| `tests/test_risk_api.py` | HTTP back-compat `{asset_portfolio, horizon}` |
| `tests/test_risk_dashboard.py` | caller presents; no bare `except Exception` |
| `tests/test_frozen.py` | `RiskResult` immutable |

Golden fixture layout:

```text
tests/fixtures/risk_golden/
  rung0_none.json
  rung1_high_risk.json
  …
```

Each file: `Scenario(portfolio, request, expected)` serialized — SDG5 seed pinned in test.

---

## 8. Explicitly out of v0 scope

- HNW compositional generator (`warehouse/research/synthetic/`)
- Rungs 3–4, cohort profiles, lot split, alt call schedules
- `RiskDeltas`, `ManifestOverlay` (contract v1)
- `cohort_id` / `generator_version` on wire (provenance v1)
- Arbitrary caller-injected assumptions
- New HTTP routes — only extend `POST /api/risk`

---

## 9. v1 bridge (after v0c ships)

1. **Rung 3** — HNW generator emits Shape A with `complexity=3`, `cohort_id`, liquidity tiers on
   slots; risk engine unchanged; golden matrix extends to `rung3 × scenarios`.
2. **Rung 4** — Shape B household fixture seeds DB for optimizer/recon; project sleeve weights to
   Shape A for risk; `concentrated_stress` cohort as SDG2 negation pack.
3. **Overlays** — contract v1; `founder_executive` concentration → `weight_tilts` overlay tests.
4. **Scenario catalog (Shape C)** — cards in `runs/research/` linking seed, cohort, generator_version
   to risk fingerprints (HNW historic backtest catalog pattern).

---

## 10. Suggested PR order

```text
PR1  v0a — service.py, RiskRequest/RiskResult, frozen registry
PR2  v0b — scenarios.py, assumptions lift, run_scenarios (part 1: base + high_risk)
PR3  v0b — low_risk, fingerprint, golden rung×scenario
PR4  v0c — synthetic.rung(0..2), adapters/ledger.py
PR5  v0c — risk_data.py slim, api.py → evaluate_risk, dashboard panel
```

Each PR: `ruff check src tests`, `mypy src/warehouse`, `pytest` green; dashboard panel still
shows risk manifest after PR5.

**After each PR:** set deliverable `status` to `shipped` (and rung `status` if applicable) in
[`risk_build_registry.py`](../src/warehouse/dashboard/risk_build_registry.py). Stakeholders
track progress at `warehouse serve --risk` → http://127.0.0.1:8765/risk or
`/api/risk/build` JSON.

---

## Iteration log

| Date | Note |
| --- | --- |
| 2026-06-26 | v1 shipped: `ManifestOverlay`, `RiskDeltas`, `apply_overlay`/`diff_reports`, `evaluate_risk(assumptions=)`, rungs 3–4, dashboard deltas panel. |
| 2026-06-26 | v0c shipped: `adapters/ledger.py` (`build_household_manifest`), slim `risk_data.py`, `evaluate_risk_http`, integration schema; golden HTTP parity. |
| 2026-06-26 | v0b shipped: `RiskAssumptions`, `scenarios.py` (base/high/low, PSD), `run_scenarios` → `RiskResult.scenarios`, regime in fingerprint, `synthetic.rung(0..2)`, golden `rung×scenario` fixtures. |
| 2026-06-26 | v0a shipped: `RiskRequest`, `RiskResult`, `ScenarioSet`, `evaluate_risk`, frozen registry, `tests/test_risk_service.py`. |
