# Investment Warehouse

Tech-enabled multi-family office platform shell. North star: **after-tax wealth
maximization** over a wealth data model (assets, entities, contracts, relationships).

Derived from the Sharpe founding investment engineer brief — see
`docs/research/sharpe_founding_engineer_brief.md`.

## Dashboard-first (do not skip)

**Every phase must ship visible dashboard state.** When the project runs, the dashboard
is the living functional status report — not a separate doc or slide deck.

```bash
warehouse serve          # http://127.0.0.1:8765/ — auto-refreshes every 30s
warehouse serve --port 9000
curl localhost:8765/api/status   # JSON status for automation
```

Rules:

- No phase closes without a new or upgraded dashboard panel reflecting **real** system state
- Panels show data from the running system (positions, breaks, proposals) — use demo/sample
  data only until ingest is live, but the panel must exist and be wired
- `warehouse.dashboard.phases` tracks panel status (`live` | `stub` | `planned`); keep aligned
  with `TODO.md`
- Prefer adding a panel over adding hidden backend-only code

Current live panels (Phase 0, complete): platform overview, phase roadmap, plane readiness,
workflow catalog, infra health. See `TODO.md` for per-phase panel deliverables.

## Public repository & early dev

This is a **public GitHub repo**. Treat it accordingly:

- **Non-secret settings** live in `configs/` — primarily `configs/development.toml` (committed)
- **Optional local overrides:** copy to `configs/local.toml` (gitignored) for machine-specific paths
- **Never commit** credentials, client data, or real custodian files
- **`runs/`**, **`data/`**, and **`*.db`** are gitignored — local state stays local
- **No Docker in Phases 0–4** — zero external services required to develop or run tests
- Override config file path: `WAREHOUSE_CONFIG=configs/staging.toml`
- Postgres, Redis, and docker-compose are **Phase 5** (prod parity, not a gate on product work)

## Build order (do not skip)

```text
Ledger + security master → entity graph → optimizer → OMS
```

Positions-first, trading-second. Do not ship OMS before reconciliation and security
master v0 are trustworthy.

## Five operational planes

| Plane | Package | Responsibility |
| --- | --- | --- |
| **Data** | `warehouse.data` | Custodian ingest, security master, lot ledger |
| **Research** | `warehouse.research` | Macro scenarios, backtests / sims (walk-forward safe) |
| **Decision** | `warehouse.decision` | IPS monitoring, tax-aware optimizer, advisor approval |
| **Execution** | `warehouse.execution` | OMS / trade staging, post-trade reconciliation |
| **Reporting** | `warehouse.reporting` | Performance, risk, tax reporting |

## Core domain models (`warehouse.models`)

- **Entity graph** — Person, Household, Trust, LLC, Account, Beneficiary, Custodian
- **Security master** — symbology, asset class, tax character, wash-sale groups
- **Lot ledger** — Account × Instrument × Lot (qty, basis, holding period, wash chains)
- **Contracts** — versioned IPS, mandates, fee schedules (effective-dated)
- **Events** — immutable transaction stream (trades, transfers, dividends, marks)
- **Simulations** — job records with input snapshot ID, config hash, projected tax ledger

## Six core workflows (`warehouse.workflows`)

1. Onboarding — entity mapping, account linking, IPS as machine-readable policy
2. Daily refresh — custodian → reconcile → lots → corporate actions → exception queue
3. Policy monitoring — drift vs IPS, concentration, liquidity
4. Research / scenario — macro what-ifs → optimizer narrative (human approval at UHNW)
5. Rebalance + tax overlay — TLH, gain deferral, asset location → advisor review
6. Alternatives — manual marks, capital calls, separate sub-ledger

## Infrastructure (`warehouse.infra`)

Early dev (Phases 0–4): SQLite ledger, local filesystem for uploads, in-process jobs.
Phase 5+: managed Postgres (ACID reconciliation), object store, Redis queue.

- Row-level security on `household_id`, immutable audit log (Postgres in Phase 5)

## Optimizer v0 (`warehouse.decision.optimizer`)

Pragmatic staged approach: ranked TLH heuristics + greedy rebalance. Documented upgrade
path to full MIP (Gurobi / CPLEX). Every output must include rationale: lots touched,
binding constraints, tax delta vs baseline.

## Research sandbox

Production client data stays isolated. Backtests use `runs/research/` with purged
walk-forward discipline (`walk_forward_purge_days` in `configs/development.toml`).

## Configuration

```text
configs/development.toml   # default — committed, not secrets
configs/local.toml         # optional machine overrides — gitignored
WAREHOUSE_CONFIG=...       # env var to point at another toml file
```

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                        # no Docker required
pytest tests/test_frozen.py   # immutability registry
warehouse serve               # living status dashboard (primary entry point)
warehouse serve --risk        # risk & synthetic build tracker landing page
warehouse db bootstrap        # migrate + seed demo household
warehouse db upgrade          # Alembic migrations only
warehouse info                # CLI summary
warehouse --help
```

## Conventions

- Walk-forward safe code — no lookahead in sims or backtests
- Version-pin tax rates, substitute groups, optimizer configs for audit replay
- Event-driven updates preferred over batch-only at scale
- Human approval gates dominate; decision support not autonomous alpha
- Propagate errors; prefer fixing one reconciliation bug over multiple optimizer tweaks

## Line length

**79 characters** — one limit, one config: `pyproject.toml` → `[tool.ruff] line-length`.
EditorConfig, VS Code rulers, and ruff format all read that. Do not maintain a second length.

Wrap imports and call sites; no `# noqa: E501`. HTML in `dashboard/render_*.py` / `server.py` may exceed 79.

## Errors bubble to surface (no silent failures)

**Never swallow errors.** Failures must propagate to the caller, the dashboard, or the CLI —
not disappear into logs or default values.

Rules:

- **No bare `except:`** or `except Exception: pass` — if you catch, re-raise or wrap with context
- **No silent fallbacks** — do not return `None`, `{}`, or zero on error when the caller expects real data
- **No default-on-failure** — e.g. do not treat a failed reconcile as "positions unchanged"
- **Propagate with context** — use `raise ... from err`; attach household_id, run_id, or file path
- **Dashboard must show failures** — ingest errors, recon breaks, optimizer failures, and job errors
  appear in status panels or an exception queue; never omit them from the living report
- **Walk-forward / audit violations** — raise (`WalkForwardError`, etc.); never clip or skip quietly

Prefer a loud failure over a wrong portfolio state.

## Heuristic frameworks

Read and apply the axiom sets in `docs/heuristics/` when reasoning in the matching
domain. Do not paste the full axioms into responses — use them as lenses.

| When you are… | Read and apply |
| --- | --- |
| Designing, reviewing, or implementing **risk** (measurement, scenarios, stress, limits, portfolio construction, `warehouse.research.risk`, risk API/dashboard) | [`docs/heuristics/Risk Management.md`](docs/heuristics/Risk%20Management.md) — RM1–RM7 (quantify, diversify, prevent, EV, tails, factor independence, controllable exposure) |
| Thinking about **repo or project organization** (where code/docs live, naming, discovery, package boundaries, docs layout) | [`docs/heuristics/Libraries.md`](docs/heuristics/Libraries.md) — HLib1–HLib6 (collocation, fixed location, hierarchy, controlled vocabulary, citation chaining, single entry point) |
| Thinking about **module or system structure** (planes, packages, APIs, dashboards, how subsystems map to reality) | [`docs/heuristics/Cartography.md`](docs/heuristics/Cartography.md) — C1–C8 (projection, scale, coordinates, purposeful omission, legend, hierarchy, orientation, self-contained maps) |

**Overlap:** Libraries and Cartography both apply to structure — Libraries for *where things
live and how they are found*; Cartography for *how the abstraction represents reality* (what
to show, distort, or omit). Risk Management applies only to the risk plane and risk-adjacent
decision work (IPS limits, stress, concentration), not general Python style.

## Frozen variables (immutability check)

Audit-critical and replay-critical objects must be **immutable after construction**.
Mutation must **raise immediately** — never fail silently or no-op.

Mark immutable types explicitly:

- `@dataclass(frozen=True)` for result/snapshot records (e.g. `BacktestResult`)
- Pydantic `model_config = ConfigDict(frozen=True)` for domain snapshots (e.g. `Event`, `Settings`)

Register every frozen type in `warehouse.integrity.frozen_registry.FROZEN_TYPES`.
**`tests/test_frozen.py`** iterates the registry and asserts `setattr` raises — run via `pytest`.

When adding a new immutable type:

1. Set `frozen=True` on the model/dataclass
2. Append the type to `FROZEN_TYPES`
3. Confirm the registry test passes

Do not mutate loaded config (`get_settings()`) or version-pinned tax/optimizer inputs in place —
build a new object via `model_copy()` if a variant is needed.

```bash
pytest tests/test_frozen.py   # frozen registry immutability
```

## Key docs

- `CI.md` — CI commands, GitHub Actions replay, pre-push checklist
- `docs/dev_contract_registry.md` — scopes, boundaries, track status (index + amendment protocol)
- `docs/research/sharpe_founding_engineer_brief.md` — platform synthesis
- `docs/heuristics/Risk Management.md` — risk reasoning axioms (RM1–RM7)
- `docs/heuristics/Libraries.md` — repo organization axioms (HLib1–HLib6)
- `docs/heuristics/Cartography.md` — module/map structure axioms (C1–C8)
- `docs/risk_api_contract.md` — risk API v0 contract
- `docs/risk_api_implementation_plan.md` — HNW-informed build plan (v0a/b/c PRs)
- `TODO.md` — phased deliverables
- `JOURNAL.md` — build log
