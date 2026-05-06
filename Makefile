# Tortilla Analytics — common dev commands.
# All commands run against the Docker compose stack.

.PHONY: help up down logs ps build rebuild reset health \
        generate etl best-sellers peak-hours comparison \
        shell-backend psql test check lint format secrets \
        seed-90d seed-1y types e2e

help:                  ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up:                    ## Bring up the stack (db + backend).
	docker compose up -d --build

down:                  ## Stop the stack.
	docker compose down

reset:                 ## Stop the stack AND wipe the database volume (destructive).
	docker compose down -v

logs:                  ## Tail backend logs.
	docker compose logs -f backend

ps:                    ## List running services.
	docker compose ps

build:                 ## Build the backend image.
	docker compose build backend

rebuild:               ## Rebuild the backend image (no cache).
	docker compose build --no-cache backend

health:                ## Hit the /health endpoint.
	curl -s http://localhost:$${BACKEND_PORT:-8000}/health | python -m json.tool

# ── ETL / data ──────────────────────────────────────────────────────────────
DATE ?= $(shell date -u +%Y-%m-%d)

generate:              ## Generate mock POS exports (override: make generate DATE=2026-05-04).
	docker compose run --rm backend python -m app.cli generate $(DATE)

etl:                   ## Load POS exports for DATE into Postgres.
	docker compose run --rm backend python -m app.cli etl $(DATE)

# ── Analytics ───────────────────────────────────────────────────────────────
FROM ?= 2026-05-01
TO   ?= 2026-05-31

best-sellers:          ## Run best-sellers (override: FROM=... TO=...).
	docker compose run --rm backend python -m app.cli analytics best_sellers $(FROM) $(TO)

peak-hours:            ## Run peak-hours.
	docker compose run --rm backend python -m app.cli analytics peak_hours $(FROM) $(TO)

comparison:            ## Run restaurant comparison.
	docker compose run --rm backend python -m app.cli analytics comparison $(FROM) $(TO)

# ── Bulk seeding ─────────────────────────────────────────────────────────────
# Generates and ETLs N days of mock POS data ending today. Used for visual
# smoke and EXPLAIN-based perf verification (plan §10).
seed-90d:              ## Generate + ETL 90 days of data ending today.
	@DAYS=90; for i in $$(seq 0 $$((DAYS-1))); do \
	    DATE=$$(python3 -c "from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(days=$$i)).strftime('%Y-%m-%d'))"); \
	    echo "── seeding $$DATE ──"; \
	    docker compose run --rm backend python -m app.cli generate $$DATE; \
	    docker compose run --rm backend python -m app.cli etl $$DATE; \
	done

seed-1y:               ## Generate + ETL 365 days of data (heavy, ~5-10 min).
	@DAYS=365; for i in $$(seq 0 $$((DAYS-1))); do \
	    DATE=$$(python3 -c "from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(days=$$i)).strftime('%Y-%m-%d'))"); \
	    docker compose run --rm backend python -m app.cli generate $$DATE >/dev/null; \
	    docker compose run --rm backend python -m app.cli etl $$DATE >/dev/null; \
	    [ $$((i % 30)) = 0 ] && echo "  $$i / $$DAYS days seeded"; \
	done; \
	echo "[DONE] $$DAYS days seeded"

# ── Frontend codegen + E2E ──────────────────────────────────────────────────
types:                 ## Regenerate frontend TS types from FastAPI's OpenAPI.
	cd frontend && pnpm run gen:types

e2e:                   ## Run Playwright E2E tests against the running stack.
	cd frontend && pnpm run e2e

# ── Dev shells ──────────────────────────────────────────────────────────────
shell-backend:         ## Open a bash shell in the backend container.
	docker compose run --rm backend bash

psql:                  ## Open a psql shell in the db container.
	docker compose exec db psql -U $${DB_USER:-tortilla_user} -d $${DB_NAME:-tortilla_db}

test:                  ## Run the import smoke test (uv on host, fast path).
	cd backend && uv run --quiet pytest -q tests/

# ── Quality gate ─────────────────────────────────────────────────────────────
# `make check` is read-only — it never modifies files. CI-friendly.
# Runs on the host via uv (fast feedback). gitleaks runs via Docker so no
# host install is needed.
check: lint secrets test  ## Run all checks: ruff (format + lint) + secrets scan + tests.

lint:                  ## Lint backend (ruff format --check + ruff check).
	cd backend && uv run --quiet ruff format --check app tests
	cd backend && uv run --quiet ruff check app tests

format:                ## Auto-format backend (ruff format + ruff check --fix).
	cd backend && uv run --quiet ruff format app tests
	cd backend && uv run --quiet ruff check --fix app tests

secrets:               ## Scan working tree for committed secrets via gitleaks.
	docker run --rm -v $(CURDIR):/repo:ro zricethezav/gitleaks:latest detect \
	    --source=/repo --no-banner --redact --exit-code=1
