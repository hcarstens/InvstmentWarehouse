# Investment Warehouse — developer entry points.
# The CI gate itself lives in scripts/ci.sh (single source of truth); these
# targets are thin, discoverable wrappers. See CI.md.

.PHONY: help setup ci lint format types test fix

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup:  ## One-time dev setup: install .[dev] + enable the pre-push hook
	pip install -e ".[dev]"
	git config core.hooksPath scripts/git-hooks
	@echo "✓ setup complete — pre-push hook active (SKIP_CI_HOOK=1 to bypass)"

ci:  ## Run the full canonical CI gate (lint + format + types + tests)
	scripts/ci.sh

lint:  ## Ruff check only
	scripts/ci.sh lint

format:  ## Ruff format --check only
	scripts/ci.sh format

types:  ## Mypy only
	scripts/ci.sh types

test:  ## Pytest + coverage report + security gates
	scripts/ci.sh test

fix:  ## Auto-fix: ruff --fix + ruff format (mutating)
	scripts/ci.sh fix
