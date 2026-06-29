# CI — commands and checks

Reference for local pre-push validation and GitHub Actions. Phases 0–4 require **no
Docker, Postgres, or Redis** — CI and `pytest` run on SQLite and in-process jobs only.

**Workflow file:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

---

## One-time setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
make setup                         # installs .[dev] + enables the pre-push hook
```

`make setup` wraps `pip install -e ".[dev]"` and
`git config core.hooksPath scripts/git-hooks`. Without `make`, run both by hand.
Run `make help` to list all targets (`ci`, `lint`, `types`, `test`, `fix`).

Optional config override (committed defaults in `configs/development.toml`):

```bash
export WAREHOUSE_CONFIG=configs/development.toml
```

---

## GitHub Actions (canonical CI)

Runs on **push** and **pull_request** to `main` (Ubuntu, Python 3.12). Three
**independent parallel jobs** so each surface reports separately — a `types`
failure never masks a `test` regression (and vice versa):

| Job | Command(s) |
| --- | --- |
| `lint` | `ruff check src tests` · `ruff format --check src tests` |
| `types` | `mypy src/warehouse` |
| `test` | `warehouse test report` · `python -m warehouse.infra.security_gate pip-audit` · `python -m warehouse.infra.security_gate detect-secrets` · upload `runs/testing/*` artifacts |

All three must pass. Each job installs `.[dev]` independently (pip-cached).
The `test` job upgrades `pip` before install, then runs the full suite with
coverage, writes the testing report artifacts, and runs the QA7 security gates.

### Replay CI locally — `scripts/ci.sh`

`scripts/ci.sh` is the **single source of truth** for the gate (local + Actions
parity). It runs all four checks, aggregates failures (one gate never masks
another), and prefers `.venv/bin` tools:

```bash
scripts/ci.sh            # run every gate, report all failures
scripts/ci.sh lint       # ruff check only
scripts/ci.sh format     # ruff format --check only
scripts/ci.sh types      # mypy only
scripts/ci.sh test       # pytest + coverage report + security gates
scripts/ci.sh security   # pip-audit + detect-secrets only
scripts/ci.sh fix        # ruff --fix + ruff format (mutating; not a gate)
```

### Pre-push hook (catch before push)

A version-controlled hook runs `scripts/ci.sh` before every push, so a red
build never reaches `main`. `make setup` enables it; or once per clone:

```bash
git config core.hooksPath scripts/git-hooks
```

Escape hatch (CI still runs server-side): `SKIP_CI_HOOK=1 git push`.

### Raw one-liner (no script)

```bash
ruff check src tests && ruff format --check src tests && mypy src/warehouse && scripts/ci.sh test
```

---

## Lint and format

Tool config: [`pyproject.toml`](pyproject.toml) → `[tool.ruff]`, `[tool.ruff.lint]`.

| Command | Purpose |
| --- | --- |
| `ruff check src tests` | Lint — **required in CI** |
| `ruff check src tests --fix` | Auto-fix import order and safe rules |
| `ruff format src tests` | Format (79-char line length) |
| `ruff format --check src tests` | Format check — **required in CI** |
| `ruff check --select E501 src tests` | Line length only (79 chars) |

### Fix and format (post-edit)

Run after every edit session — auto-fixes import order (I001) and applies
formatter layout (E302 blank lines, wraps):

```bash
ruff check src tests --fix && ruff format src tests
```

Check-only (matches CI):

```bash
ruff check src tests && ruff format --check src tests
```

**Line length (E501):** enforced by ruff and Flake8 (`.flake8`). Dashboard HTML
modules (`render_*.py`, `server.py`, `phases.py`, `status.py`) are exempt per
`[tool.ruff.lint.per-file-ignores]` — see `CLAUDE.md`.

**Scope note:** CI lints `src` and `tests` only. Alembic migrations under
`alembic/versions/` are excluded; run `ruff check .` locally if you change migrations.

---

## Type checking

Strict mypy on the `warehouse` package (`[tool.mypy]` in `pyproject.toml`).

| Command | Purpose |
| --- | --- |
| `mypy src/warehouse` | **CI command** |
| `mypy src` | Equivalent local check (121+ modules) |

---

## Tests

Config: `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["src"]`.

| Command | Purpose |
| --- | --- |
| `warehouse test report` | Full suite + coverage JSON + `last_report.json` + `e2e_smoke.json` — **CI test job** |
| `warehouse test mutation` | Scoped `mutmut` on Data + Decision targets → `mutation_report.json` — **on-demand / nightly only** (minutes; not PR path) |
| `warehouse test report --mutation` | Run mutation first, then full report (merges kill % when artifact present) |
| `pytest` | Full suite (no coverage artifact) |
| `pytest -q` | Quiet summary |
| `pytest -x` | Stop on first failure |
| `pytest tests/test_frozen.py` | Immutability registry (`FROZEN_TYPES`) |
| `pytest --cov=warehouse --cov-report=term-missing` | Coverage terminal report |
| `pytest --cov=warehouse --cov-report=json:runs/testing/coverage.json` | Coverage JSON only (same path as CI) |

### Testing artifacts (st3–st4)

Written by `warehouse test report` (gitignored under `runs/`):

| Path | Purpose |
| --- | --- |
| `runs/testing/coverage.json` | Full `pytest-cov` JSON — per-plane bucket source |
| `runs/testing/last_report.json` | `TestingReport` for `/testing` and `GET /api/testing` |
| `runs/testing/e2e_smoke.json` | E2E smoke matrix for Research panel + `e2e_smoke` headline on `/testing` |
| `runs/testing/mutation_report.json` | Mutation kill % per critical plane (Data, Decision); merged into `last_report.json` when present |

CI uploads coverage + report + e2e artifacts (7-day retention). Mutation artifact is
**local/on-demand** — not produced by the default PR `warehouse test report` job.
Coverage
**never gates** `ok` on the dashboard (ST3) — amber badges only when below floor.
E2E smoke pass rate (`passed/households`, target 4/4) **does** gate `e2e_smoke.ok`
and contributes to `overall.ok`.

### E2E smoke falsifier (st4)

```bash
pytest tests/integration/test_end_to_end_synthetic.py tests/test_e2e_smoke.py -q
```

Structural prerequisite bundle (§4.2.1 — gate E2E):

```bash
pytest tests/test_hnw_synthetic.py tests/test_synthetic_ips*.py tests/test_ips_*.py -q
```

### Security gates (QA7, st3)

Run on every PR in the `test` job and via `scripts/ci.sh test` / `security`:

| Command | Purpose |
| --- | --- |
| `python -m warehouse.infra.security_gate pip-audit` | Fail on **HIGH/CRITICAL** dependency vulns (OSV severity) |
| `python -m warehouse.infra.security_gate detect-secrets` | Fail when new secrets appear vs `.secrets.baseline` |

Dev dependencies: `pip-audit`, `detect-secrets` in `[project.optional-dependencies] dev`.

### `/api/testing` smoke

With `warehouse serve` running:

```bash
curl -s http://127.0.0.1:8765/api/testing | python -m json.tool
```

Returns the same `TestingReport` JSON shape as `runs/testing/last_report.json`
when populated; empty-state shape is valid before the first `warehouse test report`.

### By plane / phase

| Area | Command |
| --- | --- |
| Architecture & config | `pytest tests/test_architecture.py tests/test_config.py` |
| Infra & dashboard | `pytest tests/test_infra_health.py tests/test_dashboard.py` |
| Phase 1 — entity graph | `pytest tests/test_phase1.py` |
| Phase 2 — ingest & recon | `pytest tests/test_phase2.py` |
| Phase 3 — IPS & optimizer | `pytest tests/test_phase3.py` |
| Phase 4 — OMS & execution | `pytest tests/test_phase4.py` |
| Risk API | `pytest tests/test_risk_api.py tests/test_risk_service.py tests/test_risk_integration.py tests/test_risk_v1.py tests/test_risk_scenarios.py tests/test_risk_observability.py tests/test_risk_synthetic.py tests/test_risk_dashboard.py` |
| HNW synthetic | `pytest tests/test_hnw_synthetic.py tests/test_risk_hnw_combinations.py tests/test_risk_asset_test_suite.py` |
| Synthetic IPS (si0–si3) | `pytest tests/test_ips_sleeves.py tests/test_ips_policy_fields.py tests/test_synthetic_ips.py tests/test_synthetic_ips_workflow.py` |
| Build tracker UI | `pytest tests/test_risk_build_dashboard.py` |
| Reporting performance (st5i) | `pytest tests/test_reporting_performance.py -q` |

### Track falsifiers (before marking deliverables shipped)

Registry: `src/warehouse/dashboard/risk_build_registry.py` — each shipped slice should
have a green `falsifier_test`:

| Deliverable | Falsifier |
| --- | --- |
| si0a — IpsSleeve enum | `pytest tests/test_ips_sleeves.py` |
| si0b — IPS policy fields | `pytest tests/test_ips_policy_fields.py` |
| si1 / si2 — emit + validate IPS | `pytest tests/test_synthetic_ips.py` |
| si3 — workflow smokes | `pytest tests/test_synthetic_ips_workflow.py` |

---

## Database (local / integration smoke)

Not required for CI (`pytest` uses fixtures and temp SQLite where needed). For manual
dashboard or CLI checks:

```bash
warehouse db bootstrap    # migrate + seed demo household (idempotent)
warehouse db upgrade      # Alembic migrations only
warehouse db seed         # demo data only
```

---

## Manual smoke checks (not in CI)

Useful after substantive changes to dashboards, HTTP adapters, or CLI:

```bash
warehouse info
warehouse db bootstrap
warehouse serve --risk    # http://127.0.0.1:8765/risk — build tracker
curl -s http://127.0.0.1:8765/api/status | python -m json.tool
curl -s http://127.0.0.1:8765/api/health
curl -s http://127.0.0.1:8765/api/risk/build | python -m json.tool
warehouse risk evaluate tests/fixtures/sample_portfolio.json --horizon 5y
```

Plane page JSON (preferred while `warehouse serve` is running):

```bash
curl -s http://127.0.0.1:8765/api/pages/data
curl -s http://127.0.0.1:8765/api/pages/decision
curl -s http://127.0.0.1:8765/api/pages/research
curl -s http://127.0.0.1:8765/api/pages/execution
curl -s http://127.0.0.1:8765/api/pages/reporting
curl -s http://127.0.0.1:8765/api/pages/infra
curl -s http://127.0.0.1:8765/api/risk
```

Legacy phase JSON (deprecated — responses include `Deprecation: true` and
`X-Deprecation-Notice: use /api/pages/…`):

```bash
curl -s -D - http://127.0.0.1:8765/api/phase1 -o /dev/null
curl -s http://127.0.0.1:8765/api/phase2
curl -s http://127.0.0.1:8765/api/phase3
curl -s http://127.0.0.1:8765/api/phase4
```

---

## Pre-push checklist

Minimum (matches GitHub Actions):

1. `ruff check src tests`
2. `ruff format --check src tests`
3. `mypy src/warehouse`
4. `scripts/ci.sh test` (pytest + coverage report + security gates)

Recommended before a PR that touches immutable types:

5. `pytest tests/test_frozen.py`

After adding imports or new modules:

```bash
ruff check src tests --fix && ruff format src tests
```

(Same as **Fix and format** above.)

---

## Out of scope (Phases 0–4)

| Item | Notes |
| --- | --- |
| Docker / docker-compose | Phase 5 prod parity |
| Postgres / Redis | Phase 5; use `pip install -e ".[infra]"` when needed |
| `ruff format --check` | Enforced in `.github/workflows/ci.yml` |
| E2E browser tests | Dashboard verified manually or via `tests/test_dashboard.py` |
| Load / perf benchmarks | Research sandbox under `runs/research/` |

---

## Related docs

- [`CLAUDE.md`](CLAUDE.md) — architecture, conventions, frozen registry
- [`README.md`](README.md) — setup and CLI overview
- [`docs/dev_contract_registry.md`](docs/dev_contract_registry.md) — deliverable tracks and falsifiers
- [`TODO.md`](TODO.md) — phased roadmap
