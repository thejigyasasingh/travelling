# Roaming & Wandering — backend
#
# The contract: a new engineer runs `make setup && make up` and has a working
# backend. Anything that needs more than that is a bug in this file.
#
# CI runs exactly the same targets as a developer does. When "it passes locally
# but fails in CI" happens, it should be an environment difference, never a
# difference in what the two actually ran.

.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

COMPOSE := docker compose
PY      := .venv/bin/python
UV      := uv

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── setup ─────────────────────────────────────────────────────────────────

.PHONY: setup
setup: keys env venv ## First-time setup: keys, .env, virtualenv
	@echo "Ready. Next: make up"

.PHONY: venv
venv: ## Create the virtualenv and install dependencies
	$(UV) venv .venv
	VIRTUAL_ENV=.venv $(UV) pip install -e ".[dev]"

.PHONY: keys
keys: ## Generate local + test JWT keypairs
	@bash scripts/generate_keys.sh

.PHONY: env
env: ## Create .env from the example if it does not exist
	@[[ -f .env ]] && echo ".env exists, leaving it alone" || cp .env.example .env

# ── running ───────────────────────────────────────────────────────────────

.PHONY: up
up: ## Start the full stack (postgres, redis, minio, api, worker, beat)
	$(COMPOSE) up -d --build
	@echo "API      http://localhost:8000/docs"
	@echo "MinIO    http://localhost:9001  (minioadmin/minioadmin)"
	@echo "Mail     http://localhost:8025"

.PHONY: down
down: ## Stop the stack, keep the data volumes
	$(COMPOSE) down

.PHONY: clean
clean: ## Stop the stack and DELETE all data volumes
	$(COMPOSE) down -v --remove-orphans

.PHONY: logs
logs: ## Tail application logs
	$(COMPOSE) logs -f api worker beat

.PHONY: dev
dev: ## Run the API on the host with auto-reload (deps still in docker)
	$(COMPOSE) up -d postgres redis minio
	$(PY) -m app.main

.PHONY: shell
shell: ## Python REPL with the app importable
	$(PY)

# ── database ──────────────────────────────────────────────────────────────

.PHONY: seed
seed: ## Create dev accounts and a demo listing (local only; safe to re-run)
	$(PY) -m app.interface.cli.main seed

.PHONY: migrate
migrate: ## Apply all migrations
	$(COMPOSE) run --rm migrate

.PHONY: migration
migration: ## Autogenerate a migration: make migration m="add bookings"
	@[[ -n "$(m)" ]] || { echo "Usage: make migration m=\"description\""; exit 1; }
	.venv/bin/alembic revision --autogenerate -m "$(m)"
	@echo
	@echo "READ THE GENERATED FILE. Autogenerate misses: renames (it emits"
	@echo "DROP + ADD, which loses data), CHECK constraints, and index"
	@echo "concurrency. The checklist is in alembic/script.py.mako."

.PHONY: downgrade
downgrade: ## Roll back one migration
	.venv/bin/alembic downgrade -1

.PHONY: migration-sql
migration-sql: ## Print the SQL a migration would run, without running it
	.venv/bin/alembic upgrade head --sql

.PHONY: psql
psql: ## Open a psql shell against the local database
	$(COMPOSE) exec postgres psql -U rw_app -d roaming_wandering

# ── quality ───────────────────────────────────────────────────────────────

.PHONY: fmt
fmt: ## Format code
	.venv/bin/ruff format src tests
	.venv/bin/ruff check --fix src tests

.PHONY: lint
lint: ## Lint without fixing (what CI runs)
	.venv/bin/ruff check src tests
	.venv/bin/ruff format --check src tests

.PHONY: types
types: ## Typecheck
	.venv/bin/mypy

.PHONY: arch
arch: ## Enforce the architecture contracts in .importlinter
	.venv/bin/lint-imports --config .importlinter

.PHONY: audit
audit: ## Check dependencies for known vulnerabilities
	.venv/bin/pip-audit --strict

.PHONY: check
check: lint types arch ## Every static check, no tests
	@echo "static checks passed"

# ── tests ─────────────────────────────────────────────────────────────────

.PHONY: test
test: ## Run the full suite with coverage
	.venv/bin/pytest --cov --cov-report=term-missing

.PHONY: test-unit
test-unit: ## Unit tests only — no containers, runs in seconds
	.venv/bin/pytest -m unit

.PHONY: test-int
test-int: ## Integration tests (starts throwaway postgres/redis containers)
	.venv/bin/pytest -m integration

.PHONY: ci
ci: check test ## Everything CI runs, in CI's order
	@echo "CI checks passed"
