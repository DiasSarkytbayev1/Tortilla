# Tortilla Restaurant Chain Analytics

A university database systems project (Harbour.Space — Data Storages course).

Simulates a multi-location tortilla restaurant chain where each location's POS
terminal exports a flat daily sales file. Those files are loaded into a
normalised PostgreSQL database and queried for chain-wide business analytics.
The repo is structured for the next step: a FastAPI backend and a React +
Recharts dashboard (see `docs/design-doc.md`).

---

## Structure

```
Tortilla/
├── backend/                # FastAPI app + ETL + analytics CLI (Python 3.12, uv)
│   ├── app/
│   │   ├── main.py           FastAPI entry — GET /health
│   │   ├── config.py         env-driven settings
│   │   ├── db.py             shared psycopg2 connection helper
│   │   ├── api/              HTTP routes (empty — first endpoint TBD)
│   │   ├── analytics/        SQL queries + display formatting
│   │   ├── etl/              load.py (CSV → Postgres) + generate.py (mock data)
│   │   └── cli.py            python -m app.cli {generate|etl|analytics}
│   ├── tests/test_imports.py smoke test
│   ├── pyproject.toml
│   ├── uv.lock
│   └── Dockerfile
├── frontend/               # placeholder (see frontend/README.md)
├── db/init/01_init.sql     # auto-applied on first Postgres boot
├── data/pos_exports/       # generated CSVs (gitignored)
├── docs/                   # PRD.md + design-doc.md
├── compose.yaml            # postgres + backend services
├── .env.example
├── Makefile                # common commands
└── README.md
```

---

## Quick start

```bash
cp .env.example .env             # edit DB_PASSWORD / SECRET_KEY if you like
docker compose up --build        # db init.sql runs automatically; backend + frontend start
make seed-90d                    # generate + ETL 90 days of mock POS data (a few minutes)
open http://localhost:5173       # log in as dev / devpass
```

`/health` returns `{"status":"ok","db":"ok"}` once Postgres is up and the
backend connects. The frontend runs at `http://localhost:5173`.

If you already have a service on ports 5432, 8000, or 5173, edit `DB_PORT` /
`BACKEND_PORT` / `FRONTEND_PORT` in `.env` before bringing up the stack.

### Default credentials
- Username: `dev`
- Password: `devpass`

Change these via psql for now (admin UI is on the roadmap, see TODOS.md). To
add another user, generate a bcrypt hash with `uv run --directory backend
python -c "from app.auth.passwords import hash_password; print(hash_password('NEWPASS'))"`
and `INSERT` it into the `users` table.

---

## What's running where

| Service | URL | Purpose |
|---|---|---|
| `frontend` | http://localhost:5173 | Vite dev server, React + shadcn/ui dashboard |
| `backend`  | http://localhost:8000 | FastAPI + ETL + analytics CLI |
| `db`       | localhost:5432         | Postgres 16, 4 dashboard indexes seeded |

Frontend talks to backend through Vite's `/api` proxy — same-origin in dev,
same-origin in prod. No CORS configured anywhere.

## Daily workflow (via Make targets)

```bash
make up                          # start the stack
make generate DATE=2026-05-04    # generate mock POS exports for a date
make etl      DATE=2026-05-04    # load that date into Postgres
make best-sellers FROM=2026-05-01 TO=2026-05-31
make peak-hours   FROM=2026-05-01 TO=2026-05-31
make comparison   FROM=2026-05-01 TO=2026-05-31
make health
make logs
make psql                        # interactive psql in the db container
make reset                       # WIPE database volume (destructive)
make help                        # full list
```

The same commands without Make:

```bash
docker compose run --rm backend python -m app.cli generate 2026-05-04
docker compose run --rm backend python -m app.cli etl 2026-05-04
docker compose run --rm backend python -m app.cli analytics best_sellers 2026-05-01 2026-05-31
```

`generate` writes to `data/pos_exports/2026-05-04/` on your host (volume-mounted
into the container at `/app/data/pos_exports`). The folder is gitignored.

---

## Data flow

```
generate  →  data/pos_exports/YYYY-MM-DD/  →  etl  →  PostgreSQL  →  analytics
 (mock POS)        (flat CSV files)         (load)   (normalised)    (queries / API)
```

1. `generate` produces one flat CSV per restaurant, mimicking a daily POS
   terminal export — one row per line item, with bill and menu fields
   denormalised alongside it.
2. `etl` reads those CSVs and populates the normalised tables (`menu_items`,
   `bills`, `bill_items`). Running it twice for the same date is safe —
   duplicates are silently skipped.
3. `analytics` runs the three core analytical queries directly against
   PostgreSQL.

---

## Database schema

Five tables. The first four are the analytical core; the last two are
operational scaffolding for the POS integration layer (see PRD §6).

```
restaurants    → id, name, city
menu_items     → id, code, name, category, price
bills          → (restaurant_id, bill_no) PK, id UK, sold_at, payment_method, total
bill_items     → id, bill_id FK→bills.id, menu_item_id FK, quantity, unit_price, line_total
pos_connectors → one connector config per restaurant
sync_runs      → execution log for each scheduled sync
```

`bill_items.unit_price` is captured at sale time, so historical revenue stays
accurate even if `menu_items.price` changes later. Revenue metrics always sum
`bill_items.line_total` at the item level and `bills.total` at the bill level —
never profit (the schema has no `cost` column).

---

## Analytical queries

| Command | Question answered |
|---|---|
| `analytics best_sellers FROM TO` | What's our best-selling dish? |
| `analytics peak_hours FROM TO` | When do we get hammered on Saturdays? |
| `analytics comparison FROM TO` | How does Restaurant A compare to B? |

Filters:

```bash
# Filter best sellers to one restaurant, top 5
make best-sellers FROM=2026-05-01 TO=2026-05-31  # then add flags via cli directly:
docker compose run --rm backend python -m app.cli analytics best_sellers \
    2026-05-01 2026-05-31 --restaurant_id 2 --top_n 5

# Filter to one menu category
docker compose run --rm backend python -m app.cli analytics best_sellers \
    2026-05-01 2026-05-31 --category tortilla
```

---

## CSV format

Each row is one line item from a bill, with bill and restaurant fields repeated
— the standard flat shape a POS terminal produces before normalisation.

```
restaurant_id, restaurant_name, restaurant_city,
bill_no, sold_at, payment_method, bill_total,
item_code, item_name, item_category,
quantity, unit_price, line_total
```

---

## Running the backend without Docker

You can also run things directly on your machine if you have a local Postgres.

```bash
cd backend
uv sync
cp ../.env.example ../.env       # or set env vars directly
# edit .env: DB_HOST=localhost
uv run uvicorn app.main:app --reload
uv run python -m app.cli generate 2026-05-04
uv run python -m app.cli etl 2026-05-04
```

---

## Schema changes after first boot

Postgres only runs `db/init/*.sql` on **first volume creation**. To re-apply
schema changes you must wipe the volume:

```bash
make reset                       # docker compose down -v
make up                          # init scripts run again
```

This is fine for a class project. For real schema evolution, add Alembic
migrations to the backend.

---

## Quality gate

`make check` runs the full read-only quality gate — lint, secrets scan, and
tests — and fails fast on any issue. Use it before every commit.

```bash
make check       # lint + secrets + test
make lint        # ruff format --check + ruff check
make format      # auto-fix formatting + safe lint issues
make secrets     # gitleaks scan (uses zricethezav/gitleaks via Docker)
make test        # import smoke test
```

`lint` and `test` run on the host via `uv` for speed (sub-second feedback);
`secrets` runs `gitleaks` in a one-shot Docker container so no host install
is needed. Ruff config lives in `backend/pyproject.toml` under `[tool.ruff]`.

For broader coverage (analytics queries against a seeded test DB, FastAPI
route assertions) — that's a follow-up.

---

## Documentation

- `docs/PRD.md` — product requirements (V1 scope, schema, milestones)
- `docs/design-doc.md` — analyst dashboard design (wireframes, SQL, API surface)

Pick **one** page from `design-doc.md` §9 and implement end-to-end as the next
slice — `Best Sellers` is recommended (smallest, exercises the full stack).
