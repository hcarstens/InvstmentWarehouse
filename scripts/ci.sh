#!/usr/bin/env bash
# Canonical CI gate — the single source of truth for local + Actions parity.
#
# Mirrors .github/workflows/ci.yml exactly: lint, format, types, tests. Runs
# ALL gates and aggregates failures (one failing gate never masks another —
# same reason CI splits them into parallel jobs). Exits non-zero if any fail.
#
# Usage:
#   scripts/ci.sh            # run every gate, report all failures
#   scripts/ci.sh lint       # ruff check only
#   scripts/ci.sh format     # ruff format --check only
#   scripts/ci.sh types      # mypy only
#   scripts/ci.sh test       # pytest + coverage report + security gates
#   scripts/ci.sh security   # pip-audit + detect-secrets only
#   scripts/ci.sh fix        # ruff --fix + ruff format (mutating; not a gate)
#
# Prefers .venv/bin tools when present, else falls back to PATH.
set -uo pipefail

cd "$(dirname "$0")/.."

# Resolve tool paths: project venv first, then PATH.
if [[ -x .venv/bin/ruff ]]; then
  BIN=.venv/bin/
else
  BIN=
fi
RUFF="${BIN}ruff"
MYPY="${BIN}mypy"
PYTHON="${BIN}python"
WAREHOUSE="${BIN}warehouse"

failures=()

run_gate() {
  # run_gate <label> <cmd...>
  local label="$1"
  shift
  printf '\n\033[1m=== %s ===\033[0m\n' "$label"
  if "$@"; then
    printf '\033[32m✓ %s passed\033[0m\n' "$label"
  else
    printf '\033[31m✗ %s FAILED\033[0m\n' "$label"
    failures+=("$label")
  fi
}

gate_lint() { run_gate "lint (ruff check)" "$RUFF" check src tests; }
gate_format() {
  run_gate "format (ruff format --check)" "$RUFF" format --check src tests
}
gate_types() { run_gate "types (mypy)" "$MYPY" src/warehouse; }
gate_security() {
  if [[ -x ${BIN}pip ]]; then
    run_gate "security (pip upgrade)" \
      "$PYTHON" -m pip install --upgrade 'pip>=26.1.2' -q
  fi
  run_gate "security (pip-audit HIGH/CRITICAL)" \
    "$PYTHON" -m warehouse.infra.security_gate pip-audit
  run_gate "security (detect-secrets)" \
    "$PYTHON" -m warehouse.infra.security_gate detect-secrets
}
gate_test() {
  mkdir -p runs/testing
  run_gate "tests (pytest + coverage + report)" "$WAREHOUSE" test report
  gate_security
}

case "${1:-all}" in
  lint) gate_lint ;;
  format) gate_format ;;
  types) gate_types ;;
  security) gate_security ;;
  test | tests) gate_test ;;
  fix)
    # Mutating convenience — auto-fix then format. Not a gate; run before push.
    "$RUFF" check src tests --fix && "$RUFF" format src tests
    exit $?
    ;;
  all)
    gate_lint
    gate_format
    gate_types
    gate_test
    ;;
  *)
    echo "unknown gate: $1 (use: all|lint|format|types|test|security|fix)" >&2
    exit 2
    ;;
esac

if ((${#failures[@]})); then
  printf '\n\033[31mCI gate failed: %s\033[0m\n' "${failures[*]}"
  exit 1
fi
printf '\n\033[32mCI gate passed.\033[0m\n'
