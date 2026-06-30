# Investment Warehouse

UHNW wealth platform with dev dashboard for stakeholders

Public repo: https://github.com/hcarstens/InvstmentWarehouse

Henry Carstens
503 701 5741
https://hcarstens.github.io

## Setup

**Python 3.12 required** (pinned in `.python-version`). CI and mypy only
exercise 3.12 — using another version risks rounding/precision differences that
pass locally but break in CI (or vice versa). Create the venv with 3.12
explicitly:

```bash
python3.12 -m venv .venv        # must be 3.12 — see .python-version
source .venv/bin/activate
pip install -e ".[dev]"
python --version                # confirm: Python 3.12.x
```

**Optional system dependency (report PDF):** external client packs render to PDF via
[Pandoc](https://pandoc.org/) — not a Python package. Install locally when you need
`external.pdf` output:

```bash
brew install pandoc          # macOS
sudo apt install pandoc      # Debian/Ubuntu
```

A PDF engine (wkhtmltopdf, weasyprint, or a LaTeX distribution) may also be required.
Markdown + `bundle.json` remain canonical without Pandoc; `report.build` fails loudly if PDF
render is attempted without it.

Config lives in `configs/development.toml` (committed, not secrets). Optional machine overrides: `configs/local.toml` (gitignored).

## CLI

Entry point: `warehouse`

```bash
warehouse --help
```

### Dashboard

```bash
warehouse serve                  # http://127.0.0.1:8765/ — living status report
warehouse serve --risk           # risk & synthetic build tracker (stakeholder view)
warehouse serve --port 9000      # custom port
warehouse info                   # platform summary in the terminal
```

The dashboard auto-refreshes every 30s. On first load it runs migrate + seed if needed.

**Useful URLs while `serve` is running:**

| URL | Description |
| --- | --- |
| `/` | Catalog — roadmap, plane cards, panel registry |
| `/data` | Data plane (entity graph, securities, positions, custodian, alts) |
| `/research` | Research plane (risk manifest, backtests) |
| `/decision` | Decision plane (IPS, optimizer, PM/advisory, analyst) |
| `/execution` | Execution plane (recon, refresh, staged orders, solver) |
| `/reporting` | Reporting plane (tax scenarios) |
| `/infra` | Infrastructure (health checks, audit log) |
| `/testing` | Testing matrix — per-plane pass/fail, coverage %, mutation kill %, pyramid mix |
| `/risk` | Risk API + HNW synthetic build tracker |
| `/data?q=VTI` | Security master filter by ticker, name, or CUSIP |
| `/data?custodian=custodian_fidelity` | Custodian selector filter |
| `/api/status` | Platform status JSON |
| `/api/testing` | Testing report JSON (same shape as `runs/testing/last_report.json`) |
| `/api/health` | Infrastructure checks (503 if any fail) |
| `/api/pages/data` | Data plane JSON bundle (preferred) |
| `/api/pages/decision` | Decision plane JSON bundle |
| `/api/pages/research` | Research plane JSON bundle |
| `/api/pages/execution` | Execution plane JSON bundle |
| `/api/pages/reporting` | Reporting plane JSON bundle |
| `/api/pages/infra` | Infra plane JSON bundle |
| `/api/phase1` … `/api/phase4` | **Deprecated** — use `/api/pages/*` (see `Deprecation` response headers) |
| `/api/risk/build` | Build tracker JSON (for CI / automation) |
| `/api/risk` | Portfolio risk schema (GET) and evaluation (POST) |
| `/docs/risk_api_contract.md` | Serve contract doc as plain text from repo |

### Execution plane (Phase 4)

```bash
warehouse approve decide <request_id>   # approval → staged orders
warehouse order list                    # staged order queue
warehouse order <order_id>              # advance to filled (--submit for submitted)
warehouse compare-solvers               # heuristic vs MIP comparison
warehouse tax-scenario                  # NIIT/AMT overlay (--amt for AMT)
warehouse ingest --custodian custodian_fidelity tests/fixtures/fidelity_positions.csv
```

Fidelity CSV uses semicolon delimiter; Schwab uses comma.

### Research plane — risk API

Evaluate portfolio risk using the unit hierarchy from `docs/research/risk_units_measures.md`:
Level 1 (σ, VaR, ES), Level 2 (% variance by class/duration), Level 3 (native sensitivities),
Level 4 (named stress replay), plus liquidity-time units. Raw allocations and horizons are
fingerprinted for replay metadata; they are not logged when `risk_log_inputs = false` in config.

```bash
warehouse risk evaluate tests/fixtures/sample_portfolio.json --horizon 5y
curl -s http://127.0.0.1:8765/api/risk                          # schema
curl -s -X POST http://127.0.0.1:8765/api/risk \
  -H 'Content-Type: application/json' \
  -d @tests/fixtures/sample_portfolio.json
```

Request body:

```json
{
  "asset_portfolio": {
    "portfolio_id": "demo",
    "allocations": [
      {"asset_class": "equity", "weight": 0.6, "liquidity_tier": 1},
      {"asset_class": "fixed_income", "weight": 0.3, "duration_years": 6.5},
      {"asset_class": "alternatives", "weight": 0.1, "duration_years": 7, "liquidity_tier": 3}
    ]
  },
  "horizon": "5y",
  "notional_usd": 10000000
}
```

Response is a **risk manifest** JSON:

| Level | Contents |
| --- | --- |
| `level_1_portfolio` | Annualized σ, horizon σ, parametric VaR/ES with `(α, h)` metadata; optional dollar tail |
| `level_2_contributions` | % portfolio variance by asset class and duration bucket |
| `level_3_sensitivities` | Native units per sleeve (β, duration, fermi) |
| `level_4_stress` | Named replay: 2008 liquidity, 2020 pandemic, 2022 inflation |
| `liquidity` | Weighted days-to-liquidate by tier |

Also includes `measurement_summary`, `model_version`, `input_fingerprint`, and `aggregation_note`.

See `docs/research/risk_units_measures.md`, `docs/research/portfolio_risk.md`, and
`docs/research/simple_risk_models.md`.

### Decision plane (Phase 3)

```bash
warehouse optimize                 # TLH + IPS rebalance → approval queue
warehouse backtest                 # walk-forward after-tax backtest
warehouse approve list             # pending optimization approvals
warehouse approve decide <request_id>   # approve (--reject to reject)
```

### Ingest & daily refresh

```bash
warehouse db bootstrap           # migrate + seed (required first time)
warehouse refresh tests/fixtures/schwab_positions.csv   # full daily refresh workflow
warehouse ingest path/to/custodian.csv                # ingest only
```

Custodian CSV columns: `account_id,ticker,quantity,as_of_date`

### Database

```bash
warehouse db bootstrap           # migrate to head + seed demo household (recommended)
warehouse db upgrade             # Alembic migrations only
warehouse db seed                # demo data only (idempotent)
warehouse db --help
```

### Report writer

```bash
warehouse report write --household hh_demo --as-of 2026-06-24
warehouse report pdf --household hh_demo              # re-render external.pdf
warehouse report month-end --all
```

Writes `runs/reports/{household}/{period}/{snapshot_id}/` — `internal.md`, `external.md`,
`bundle.json`, and `external.pdf` (when Pandoc is available).

SQLite file: `data/warehouse_dev.db` (gitignored).

**No Docker required** through Phase 4 — the platform runs on SQLite, local files, and
in-process jobs (`warehouse serve` and `pytest` need zero external services). Phases 0–3
validated this architecture end-to-end (ingest → ledger → optimizer → approval). Phase 4
product work (OMS, MIP, multi-custodian, alternatives, tax depth) continues on the same
stack. **docker-compose, Postgres, Redis, and object store** move to **Phase 5** for prod
parity when pilot scale demands it (concurrency, RLS, background jobs) — not as a gate on
shipping product panels.

### Development

```bash
pytest                           # full test suite (no coverage artifact)
warehouse test report            # suite + artifacts for /testing dashboard
pytest tests/test_frozen.py      # immutability registry
ruff check src tests --fix && ruff format src tests   # fix and format
ruff check src tests
```

See [Testing platform](#testing-platform) below and [`CI.md`](CI.md) for coverage artifacts,
security gates, and the canonical pre-push gate (`ruff` · `mypy` · `pytest`).

## Testing platform

The testing dashboard is **living system state**, not a separate spreadsheet. A permanent
**scaffold** (registry, `/testing` page, per-plane QA footnotes, `GET /api/testing`) is
continuously fed by a **single-pass artifact generator** — run locally or let CI produce it
on each PR. You refresh the report periodically; the scaffold displays the last result.

### Run locally

```bash
warehouse test report              # full pytest + coverage → runs/testing/last_report.json
warehouse test mutation            # mutmut on Data + Decision (on-demand; minutes)
warehouse test report --mutation   # mutation first, then full report (merges kill %)
pytest                             # run tests only — no dashboard artifact
```

Artifacts (gitignored under `runs/testing/`):

| File | Purpose |
| --- | --- |
| `last_report.json` | Per-plane pass/fail, coverage %, mutation kill %, pyramid mix |
| `coverage.json` | Full `pytest-cov` JSON for drill-down |
| `e2e_smoke.json` | E2E smoke matrix (4 cohorts) |
| `mutation_report.json` | Kill % on critical planes (when mutation was run) |

Then start the dashboard — it reads the artifact; it does **not** re-run the full suite on
page load:

```bash
warehouse serve
open http://127.0.0.1:8765/testing    # consolidated matrix
```

If `last_report.json` is missing, `/testing` shows an empty state with instructions to run
`warehouse test report`. If the artifact's `git_sha` ≠ current `HEAD`, panels show a
**stale** badge with last-known metrics until you refresh.

### View results

| Where | What you see |
| --- | --- |
| `/testing` | Consolidated matrix: pass/fail per plane, coverage % (amber if below floor), mutation kill % on Data + Decision, actual-vs-target pyramid, E2E smoke pass rate |
| `/api/testing` | Same data as JSON for automation |
| `/data`, `/research`, `/decision`, `/execution`, `/reporting`, `/infra` | One-line **QA footnote** at the bottom of each plane page — that plane's tests and coverage without leaving the page |

**`ok` semantics:** coverage % is an amber **gap-finder badge only** — it never gates `ok`.
`ok` flips red solely on test failures (and E2E smoke when present). Discriminating power
comes from **mutation kill %** (report-only, not gated) and **property-based invariants**
(`hypothesis` suites on optimizer, lot, and risk math).

### CI (every PR)

The `test` job runs `warehouse test report` (full `pytest --cov=warehouse`), uploads
`coverage.json` and `last_report.json` as artifacts (7-day retention), and runs a **security
gate** (`pip-audit` + `detect-secrets`) — high/critical vulns or leaked secrets fail the job.
Mutation testing stays **on-demand** (not on the PR critical path).

**Pre-push is fast-only.** The local pre-push hook runs just `ruff check` +
`ruff format --check` (~0.08s, no network) — the full gate already runs
server-side on every push, so the hook stays off your critical path. Escape
hatch: `SKIP_CI_HOOK=1 git push`.

**End-of-day full gate.** Run the complete gate (lint → format → mypy → tests →
security) locally before signing off or opening a risky PR:

```bash
scripts/ci.sh fix && scripts/ci.sh
```

`scripts/ci.sh fix` auto-fixes import order + formatting (mutating); `scripts/ci.sh`
then runs every gate and aggregates failures. This path hits the network for
`pip-audit` — that's fine end-of-day; only the per-push hook is kept
network-free.

See [`CI.md`](CI.md) for the full command reference and [`docs/software_testing_implementation.md`](docs/software_testing_implementation.md) for the implementation plan.

## Project docs

- `CI.md` — CI commands, testing artifacts, security gates, pre-push checklist
- `docs/software_testing_implementation.md` — testing dashboard implementation plan
- `CLAUDE.md` — architecture and conventions
- `TODO.md` — phased deliverables
- `JOURNAL.md` — build log
