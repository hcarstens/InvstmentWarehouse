# Investment Warehouse

UHNW wealth platform — positions-first, dashboard-driven, after-tax north star.

Public repo: https://github.com/hcarstens/InvstmentWarehouse

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Config lives in `configs/development.toml` (committed, not secrets). Optional machine overrides: `configs/local.toml` (gitignored).

## CLI

Entry point: `warehouse`

```bash
warehouse --help
```

### Dashboard

```bash
warehouse serve                  # http://127.0.0.1:8765/ — living status report
warehouse serve --port 9000      # custom port
warehouse info                   # platform summary in the terminal
```

The dashboard auto-refreshes every 30s. On first load it runs migrate + seed if needed.

**Useful URLs while `serve` is running:**

| URL | Description |
| --- | --- |
| `/` | Full dashboard (entity graph, securities, schema status) |
| `/?q=VTI` | Security master filter by ticker, name, or CUSIP |
| `/api/status` | Platform status JSON |
| `/api/health` | Infrastructure checks (503 if any fail) |
| `/api/phase1` | Entity graph, securities, schema JSON |
| `/api/phase2` | Ingest, positions, reconciliation, refresh, audit JSON |
| `/api/phase3` | IPS drift, optimizer, approval queue, backtest JSON |
| `/api/phase4` | Staged orders, solver comparison, custodian, alts, tax JSON |
| `/?custodian=custodian_fidelity` | Filter Phase 4 custodian panel |

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
pytest                           # full test suite
pytest tests/test_frozen.py      # immutability registry
ruff check src tests
```

## Project docs

- `CLAUDE.md` — architecture and conventions
- `TODO.md` — phased deliverables
- `JOURNAL.md` — build log
