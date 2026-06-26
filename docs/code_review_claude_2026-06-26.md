# Code Review — Investment Warehouse

**Reviewer:** Claude (Opus 4.8)
**Date:** 2026-06-26
**Scope:** Full repo, framed against `docs/research/` intent and the `CLAUDE.md` conventions.
**Method:** Parallel plane-by-plane review (data / decision-execution / risk) + objective
toolchain signal (pytest, ruff, mypy). Top findings verified by reading the code directly.

---

## Overall

Genuinely impressive scaffolding. The architecture mirrors the Sharpe brief faithfully — five
planes, positions-first build order, dashboard-per-phase discipline, frozen-registry and
"errors bubble" conventions all present and mostly honored. The full suite passes in ~1s with
zero external services, exactly as the public-repo / no-Docker constraint requires. The bones
are good. The gaps are in **correctness of the financial math** and a few **principle
violations the conventions explicitly forbid** — concentrated in the newest code (decision +
risk planes).

**Status legend:** ✅ fixed this pass · ☐ open

---

## Meta findings (toolchain)

- ✅ **mypy strict re-enabled.** Added empty `src/warehouse/py.typed`, `package-data` in
  `pyproject.toml`, and `mypy src/warehouse` to `.github/workflows/ci.yml`. Running `mypy`
  without a path still warns on the package marker; CI and local checks should use
  `mypy src/warehouse`.
- ☐ **`ruff check .` fails with 2 errors** (E501 in `alembic/versions/002_phase2_ops.py:39`
  and `004_phase4_execution.py:76`). **CI runs `ruff check src tests` only** — migrations are
  out of scope until added to `per-file-ignores` or wrapped.

---

## High severity

### 1. ✅ OMS approval gate was bypassable — FIXED
`src/warehouse/execution/oms/service.py:36` `stage_orders_from_approval` checked only that the
approval row *existed*, never that `status == APPROVED`. It was gated solely because the
approval service happened to call it inside an `if APPROVED` branch — any other caller (CLI,
test, future API) could stage live orders from a PENDING/REJECTED request. Directly violated
"human approval gates dominate."

**Fix:** enforce the gate at the OMS boundary — raise `ValueError` unless
`approval.status == ApprovalStatus.APPROVED.value`. Regression test
`tests/test_phase4.py::test_oms_gate_blocks_unapproved_staging` asserts staging a PENDING
approval raises and leaks no order for that request.

### 2. ✅ Wash-sale avoidance was a label, not logic — FIXED
The optimizer harvested every loss lot with no 30-day / substitute-group / cross-account check;
`constraints.py` emitted the string `"wash_sale_30d:monitor"` but nothing enforced it, and the
`wash_sale_substitute_group` column already on `SecurityRow` was never read by the decision
plane. For a TLH product this was the core correctness gap.

**Fix:**
- Threaded `wash_sale_substitute_group` through `LotPositionView` from the security master
  (`data/ledger/views.py`).
- Added `evaluate_wash_sale_risk(lot, positions, *, as_of, window_days=30)` in `constraints.py`:
  flags a harvest when a substantially-identical lot (same security **or** same substitute
  group) was acquired within ±30 days, in any household account.
- Wired enforcement into **both** `heuristics.py` and `mip.py` — a flagged lot is skipped and
  its trigger recorded in `binding_constraints`.
- Relabeled the constraint summary `wash_sale_30d:enforced`.
- Regression test `tests/test_phase3.py::test_wash_sale_blocks_harvest_with_recent_substitute`.

**Note / follow-up:** the check keys off lot acquisition dates in the *current* positions set —
it does not yet see the immutable event stream, so a same-day-closed round-trip that left no
open replacement lot won't be caught. Wiring the trade/event history in is the natural v1.

### 3. ✅ Tax-delta helper was a dead no-op — FIXED
`heuristics.py:21` `return gain * rate if gain > 0 else gain * rate` — both branches identical,
sign convention undocumented.

**Fix:** collapsed to `return gain * rate` with a docstring fixing the convention: positive =
additional tax owed, negative = tax reduced (harvested loss lowers `estimated_tax_delta` — a
negative delta is the after-tax benefit). Matches the existing
`test_phase3.py::test_optimizer_harvests_loss_lot` assertion that the delta is `< 0`.

### 4. ✅ Reconciliation ignores `as_of_date` — FIXED
`execution/reconciliation/service.py`. The custodian field was ingested but never compared, so a
**stale custodian file reconciled "clean"** — undermining the positions-trust gate.

**Fix:**
- `ReconcileAsOfError` raised when rows have mixed `as_of_date`, when `as_of_date` is after the
  reference market date, or when older than `reconcile_max_stale_days` (default 7) vs
  `max(MarketPriceRow.as_of_date)`.
- `reconcile_ingest` returns `ReconcileResult(as_of_date, breaks)`; daily refresh step detail
  includes `as_of=…`; audit action `reconcile_as_of_ok` records dates.
- Regression tests in `tests/test_phase2.py` (fresh, stale, mixed).

### 5. ✅ Risk dashboard swallows all errors — FIXED
`dashboard/risk_data.py`. Bare `except Exception` returned a benign object with `report=None`.

**Fix:** catch domain errors only (`ValueError`, `RiskApiError`, `ValidationError`); programming
bugs (`KeyError`, `AttributeError`, etc.) bubble. Regression tests in
`tests/test_risk_dashboard.py`.

---

## Medium severity (all open)

- **Re-running reconcile duplicates breaks** and resurrects resolved ones — no uniqueness on
  `(ingest_run_id, account_id, security_id)`, no clear-before-insert
  (`reconciliation/service.py:54`).
- **Audit log isn't actually immutable** — `AuditEntry` is a plain mutable `BaseModel`, not
  `frozen=True`, and absent from `FROZEN_TYPES`, so `test_frozen.py` never checks the one thing
  the module docstring promises.
- **Risk result types not frozen/registered** — `RiskMetric`, `PortfolioRiskReport`,
  `StressScenarioResult` etc. are mutable; the two frozen dataclasses in `covariance.py` aren't
  in the registry. Audit/replay-critical snapshots per the project's own rule.
- **IPS min/max constraints are advisory only** — breaches get added to a `binding` list but no
  trade is blocked or generated; the "greedy rebalance" in the docstring doesn't exist (no
  `side="buy"` anywhere). Either implement it or stop labeling it enforcement. No infeasibility
  path — conflicting constraints yield a silent `no_action` rather than a raised typed error.
- **Tax overlays are mathematically wrong** — NIIT/AMT applied as flat additive rates with no
  thresholds/exemptions and no AMT-vs-regular `max()`; QSBS/DNI are blanket multipliers on total
  tax rather than on the qualifying gain. Rates *are* version-pinned (good), but the numbers
  aren't defensible — label as rough planning or fix the model.
- **ES contribution faked as variance contribution** — `by_class.py:64` sets
  `pct_es_contribution = pct_var`, the exact "false commensurability" the risk-units doc warns
  against. Either compute it or tag it an approximation.
- **Asset class is a hardcoded `{VTI,BND}` allowlist** in three places (`heuristics`, `mip`,
  `monitor`) — every other holding is mislabeled "equity," so all drift/allocation math is wrong
  for a real portfolio. The real `asset_class` lives on `SecurityRow`, ignored. (Now that
  `LotPositionView` carries the substitute group, threading `asset_class` through the same path
  is a small follow-on.)

---

## Low severity (all open)

- **Backtest harness is still a stub** — `research/backtest/harness.py` accepts
  `start_date`/`end_date` but does not drive a true walk-forward simulation; tax baseline is now
  consistent (`gross_return - tax_drag` on positive net gain) but the path is not replay-safe for
  research claims until dates and purge windows bind the loop.
- Duration-bucket variance shares can exceed 100% on duplicate asset classes (`by_duration.py:35`).
- CSV parsers reject `$` / thousands-comma / parenthesis-negative formats (loud failure, but
  brittle for real custodian exports); hard-coded `utf-8` (no BOM handling).
- `window_days=252` risk metadata is cosmetic — no real estimation window behind it; the
  disclosure overstates rigor.
- MIP-vs-heuristic comparison is apples-to-oranges (different trade caps — MIP capped at
  `mip_max_trades`, heuristic uncapped).
- No unique constraints on `lots` or `entity_relationships`; `list_ingest_runs_for_custodian`
  filters in Python with a `limit*3` heuristic that can under-return.
- ES multiplier for α=0.95 is off in the 6th decimal (`assumptions.py:81`, `2.062671` vs
  `2.062713`) — a version-pinned audit constant.

---

## What's genuinely good

- Variance/Euler risk-contribution math is correct and sums to 100%; σ annualization and
  α/horizon metadata travel on every `RiskMetric`.
- The ingest→ledger→reconcile path **does** raise on parse errors, unknown tickers, and missing
  files, writing `*_failed` audit rows — "errors bubble" is honored there.
- Money is `Decimal`/`Numeric` end-to-end — no float-money bug anywhere.
- Stress replay is honestly self-labeled (`linear_sleeve_shock_sum_no_cross_gamma`).
- Risk API layer maps errors to 400/422 correctly with no fallback.

---

## Recommended order from here

1. **Dup-break guard on reconcile** — no uniqueness on `(ingest_run_id, account_id, security_id)`.
2. **Frozen/registry gaps on risk types** — bring audit-critical snapshots in line with
   `FROZEN_TYPES`.
3. **Tax-overlay math** — the difference between "looks like a tax platform" and "is one."
4. **Backtest walk-forward** — wire `start_date`/`end_date` and purge into the harness loop.
5. **Risk orchestrator** — see `docs/risk_api_contract.md` for collapsing transactional flow to
   `evaluate_risk(request, manifest) → {report, deltas}`.

---

## Cross-references

- **Risk API contract / orchestrator sketch:** `docs/risk_api_contract.md` — proposed manifest
  inputs, stale marks, assessment deltas, and HTTP `POST /api/risk/orchestrate` shape.
- **Risk unit hierarchy (Levels 1–4):** `docs/research/risk_units_measures.md`,
  `docs/research/portfolio_risk.md`.
- **CI scope:** `ruff check src tests`, `mypy src/warehouse`, `pytest` — alembic migrations not
  linted unless `ruff check .` is adopted repo-wide.

---

### Changes landed this pass

| File | Change |
| --- | --- |
| `execution/oms/service.py` | Enforce APPROVED gate before staging |
| `decision/constraints.py` | `evaluate_wash_sale_risk` + substitute-group identity; `enforced` label |
| `decision/optimizer/heuristics.py` | Wire wash-sale guard; fix tax-delta no-op + document sign |
| `decision/optimizer/mip.py` | Wire wash-sale guard |
| `data/ledger/views.py` | Thread `wash_sale_substitute_group` into `LotPositionView` |
| `src/warehouse/py.typed` | PEP 561 marker for strict mypy |
| `pyproject.toml` | `package-data` for `py.typed` |
| `.github/workflows/ci.yml` | `mypy src/warehouse` job step |
| `execution/reconciliation/service.py` | `as_of_date` freshness gate; `ReconcileResult` |
| `workflows/daily_refresh.py` | Surface reconcile `as_of` in step detail |
| `dashboard/risk_data.py` | Narrow exception handling to domain errors |
| `config.py`, `configs/development.toml` | `reconcile_max_stale_days` |
| `data/ingest/runner.py` | `session.flush()` after custodian rows (autoflush=False) |
| `tests/test_phase3.py`, `tests/test_phase4.py`, `tests/test_risk_dashboard.py` | Regression tests + new required field |
| `tests/test_phase2.py` | Reconcile freshness tests (fresh / stale / mixed) |
| `tests/test_config.py` | Assert `reconcile_max_stale_days` |

**Verification:** `pytest` 72 passed; `ruff check src tests` clean; `mypy src/warehouse`
success (pre-existing alembic E501s remain outside CI scope, see meta findings).
