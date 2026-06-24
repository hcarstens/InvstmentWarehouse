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
