# Tortilla Restaurant Chain Analytics

A university database systems project (Harbour.Space — Data Storages course).

Simulates a multi-location tortilla restaurant chain. Each location's POS
terminal exports a flat daily sales file. Those files are loaded into a
normalised PostgreSQL database. A FastAPI backend serves analytical queries,
and a React + shadcn/ui dashboard answers chain-wide business questions:
best-selling dish, peak hours, restaurant-by-restaurant comparison.

See `docs/PRD.md` for the product spec and `docs/design-doc.md` for the
dashboard design (wireframes, SQL, API surface).

---

## Quick start

```bash
git clone …
cd Tortilla
cp .env.example .env             # edit DB_PASSWORD / SECRET_KEY for prod
docker compose up --build        # starts db + backend + frontend
make seed-90d                    # generate + ETL 90 days of mock POS data (~3-5 min)
open http://localhost:5173       # log in as dev / devpass
```

That's it. The schema, indexes, and dev user are seeded automatically the
first time the `db` container creates its volume.

| Service    | URL                       | What it does                                  |
|------------|---------------------------|------------------------------------------------|
| `frontend` | http://localhost:5173     | Vite dev server, React + shadcn/ui dashboard  |
| `backend`  | http://localhost:8000     | FastAPI app + ETL/analytics CLI               |
| `db`       | localhost:5432            | Postgres 16 + auto-applied schema             |

`/health` returns `{"status":"ok","db":"ok"}` once Postgres is up and the
backend has connected. The frontend talks to the backend via Vite's `/api`
proxy — same-origin in dev, same-origin in prod, no CORS configured anywhere.

If port 5432, 8000, or 5173 is already in use on your host, edit the
matching `*_PORT` entry in `.env` before bringing up the stack.

### Default credentials

- Username: `dev`
- Password: `devpass`

To add a real user, generate a bcrypt hash and `INSERT` into `users`:

```bash
docker compose exec backend \
  python -c "from app.auth.passwords import hash_password; print(hash_password('NEWPASS'))"

# then
make psql
INSERT INTO users (username, password_hash, role)
VALUES ('alice', '$2b$12$...the-hash-from-above...', 'analyst');
```

(Admin UI for user management is on the roadmap — see `TODOS.md`.)

---

## Project structure

```
Tortilla/
├── backend/                          FastAPI + ETL + analytics CLI (Python 3.14, uv)
│   ├── app/
│   │   ├── main.py                   FastAPI entry, mounts /api router
│   │   ├── config.py                 env-driven settings (DB, SECRET_KEY, CHAIN_TZ, …)
│   │   ├── db.py                     shared psycopg2 connection helper
│   │   ├── cli.py                    `python -m app.cli {generate|etl|analytics}`
│   │   ├── validation.py             date-range guard rails (rejects > 2y, from > to, …)
│   │   ├── api/                      HTTP routes
│   │   │   ├── router.py             composes public + protected /api routers
│   │   │   ├── deps.py               require_user, CommonFilters dependencies
│   │   │   ├── auth.py               POST /api/auth/{login,logout}, GET /api/auth/me
│   │   │   ├── meta.py               GET /api/restaurants, GET /api/categories
│   │   │   ├── overview.py           GET /api/overview/{kpis,trend}
│   │   │   ├── best_sellers.py       GET /api/best-sellers
│   │   │   ├── time_series.py        GET /api/time-series
│   │   │   ├── peak_hours.py         GET /api/peak-hours
│   │   │   └── comparison.py         GET /api/comparison
│   │   ├── auth/
│   │   │   ├── passwords.py          bcrypt hash + verify
│   │   │   └── users.py              user lookup
│   │   ├── analytics/
│   │   │   ├── sql.py                pure SQL functions, return list[dict]
│   │   │   └── queries.py            same SQL with print/DataFrame for the CLI
│   │   └── etl/
│   │       ├── generate.py           mock POS export generator (faker)
│   │       └── load.py               idempotent CSV → Postgres loader
│   ├── tests/                        9 test files, 41 tests (pytest)
│   │   ├── conftest.py               db fixtures, authed_client, isolated_data
│   │   ├── test_auth.py
│   │   ├── test_validation.py
│   │   ├── test_meta.py
│   │   ├── test_overview.py
│   │   ├── test_best_sellers.py
│   │   ├── test_time_series.py
│   │   ├── test_peak_hours.py
│   │   ├── test_comparison.py
│   │   └── test_imports.py
│   ├── pyproject.toml                deps managed by uv
│   ├── uv.lock
│   └── Dockerfile                    multi-stage uv build
│
├── frontend/                         React + shadcn/ui dashboard (Vite, Node 22, pnpm)
│   ├── src/
│   │   ├── main.tsx                  entry: BrowserRouter + NuqsAdapter + QueryClient
│   │   ├── App.tsx                   route table; ProtectedRoute around all dashboard pages
│   │   ├── index.css                 Tailwind v4 + shadcn theme tokens
│   │   ├── api/
│   │   │   ├── client.ts             openapi-fetch wrapper, sends cookies
│   │   │   ├── types.ts              auto-generated by `make types`
│   │   │   └── schemas.ts            named-type aliases (don't get clobbered on regen)
│   │   ├── auth/
│   │   │   ├── AuthProvider.tsx      session state, login(), logout()
│   │   │   └── ProtectedRoute.tsx    redirect-to-login wrapper
│   │   ├── hooks/
│   │   │   └── useFilters.ts         URL-synced global filter state via nuqs
│   │   ├── lib/
│   │   │   ├── format.ts             currency/date/delta formatters
│   │   │   ├── periods.ts            preset ranges (Last 7d, MTD, YTD, …) + validation
│   │   │   └── utils.ts              cn() classname helper
│   │   ├── components/
│   │   │   ├── ui/                   14 shadcn primitives (Button, Card, Calendar, …)
│   │   │   ├── FilterBar.tsx         global filter: date range + restaurants + categories
│   │   │   ├── KPICard.tsx           KPI value + delta arrow + colour
│   │   │   ├── ChartShell.tsx        loading/empty/error wrapper for any chart
│   │   │   ├── RevenueLineChart.tsx  Recharts line chart with optional overlay
│   │   │   ├── RankedBarChart.tsx    Recharts horizontal bar chart
│   │   │   └── DOWHourHeatmap.tsx    custom 7×24 SVG heatmap (Recharts has none)
│   │   ├── pages/
│   │   │   ├── Login.tsx             POST /api/auth/login → cookie set
│   │   │   ├── Layout.tsx            top nav (5 tabs) + global FilterBar + <Outlet/>
│   │   │   ├── Overview.tsx          5 KPIs + chain-wide revenue trend
│   │   │   ├── BestSellers.tsx       ranked bar + sortable table, qty/revenue toggle
│   │   │   ├── TimeSeries.tsx        granularity radio + previous-period overlay
│   │   │   ├── PeakHours.tsx         heatmap + hourly-bars tabs
│   │   │   └── Comparison.tsx        KPI matrix + ranked bars + overlaid trend lines
│   │   └── tests/                    Vitest, 28 tests
│   │       ├── format.test.ts
│   │       └── periods.test.ts
│   ├── components.json               shadcn config
│   ├── vite.config.ts                /api → backend:8000 proxy
│   ├── tailwind.config / index.css   Tailwind v4
│   ├── package.json + pnpm-lock.yaml
│   └── Dockerfile                    Node 22 alpine + pnpm via corepack
│
├── db/init/
│   ├── 01_init.sql                   schema, 4 dashboard indexes, restaurant + menu seed
│   └── 02_users.sql                  users table + bcrypt-seeded `dev` user
│
├── data/pos_exports/                 generated CSVs (gitignored, mounted into backend)
│
├── docs/
│   ├── PRD.md                        product spec, V1 scope
│   └── design-doc.md                 dashboard design: wireframes, SQL, API surface
│
├── compose.yaml                      db + backend + frontend services
├── Makefile                          all the common commands (`make help`)
├── .env.example                      copy to .env
├── TODOS.md                          deferred work with full context per item
└── LICENSE
```

---

## Running with Docker Compose

The whole stack runs through `compose.yaml`. Three services:

```
┌────────────────────┐  Vite proxy  ┌────────────────────┐  psycopg2  ┌──────────────┐
│ frontend           │  /api/* →    │ backend            │  ────────► │ db           │
│ vite dev :5173     │              │ uvicorn :8000      │            │ postgres :5432│
│ React+shadcn       │              │ FastAPI + auth     │            │ + init.sql   │
└────────────────────┘              └────────────────────┘            └──────────────┘
        ▲                                       ▲
        │ host volume mount                     │ host volume mount
        ./frontend                              ./data → /app/data
```

### First boot

```bash
cp .env.example .env
docker compose up --build
```

- `db` runs both `db/init/01_init.sql` and `db/init/02_users.sql` automatically
  on **first** volume creation. They're idempotent (`IF NOT EXISTS` everywhere).
- `backend` waits for the db's healthcheck to pass before starting.
- `frontend` waits for the backend, mounts `./frontend` for hot-reload, and
  proxies `/api` calls through to the backend container.

### Day-to-day

```bash
make up                       # docker compose up -d --build
make logs                     # tail backend logs
make ps                       # service status
make down                     # stop everything (data preserved)
make reset                    # ⚠️  stop + WIPE volume (init scripts re-run on next up)
```

### Run a one-off command in the backend container

```bash
docker compose run --rm backend python -m app.cli generate 2026-05-04
docker compose run --rm backend python -m app.cli etl 2026-05-04
docker compose run --rm backend python -m app.cli analytics best_sellers 2026-05-01 2026-05-31
```

`docker compose run --rm` spins up a one-shot container that's removed when
the command exits. The mounted `./data` volume persists the generated CSVs
on the host, so subsequent `etl` runs can read them.

### Schema changes after first boot

Postgres only runs `db/init/*.sql` once, on first volume creation. To pick
up a schema change you must wipe the volume:

```bash
make reset && make up         # destroys all data, runs init scripts fresh
```

(For real schema evolution, add Alembic migrations — see `TODOS.md::alembic`.)

---

## Daily workflow (Make targets)

```bash
make up                                  # start db + backend + frontend
make health                              # GET /health, expect {"status":"ok"}
make generate DATE=2026-05-04            # mock POS exports for one date
make etl      DATE=2026-05-04            # load that date into Postgres
make seed-90d                            # generate + ETL 90 days (a few min)
make seed-1y                             # generate + ETL 365 days (~10 min)
make best-sellers FROM=2026-05-01 TO=2026-05-31
make peak-hours   FROM=2026-05-01 TO=2026-05-31
make comparison   FROM=2026-05-01 TO=2026-05-31
make types                               # regen frontend OpenAPI types from /openapi.json
make psql                                # interactive psql in the db container
make shell-backend                       # bash inside backend container
make logs                                # follow backend logs
make help                                # full target list
```

For analytics CLI flags (filter to one restaurant, change top_n, …):

```bash
docker compose run --rm backend python -m app.cli analytics best_sellers \
    2026-05-01 2026-05-31 --restaurant_id 2 --top_n 5

docker compose run --rm backend python -m app.cli analytics best_sellers \
    2026-05-01 2026-05-31 --category tortilla
```

---

## Data flow

```
generate  →  data/pos_exports/YYYY-MM-DD/  →  etl  →  PostgreSQL  →  FastAPI  →  Dashboard
 (mock POS)        (flat CSV files)         (load)   (normalised)    (/api)      (shadcn)
```

1. `generate` produces one flat CSV per restaurant per day, mimicking a POS
   terminal export. Bill and menu fields are denormalised onto every line
   item — exactly what real POS exports look like.
2. `etl` reads those CSVs and populates `menu_items`, `bills`, `bill_items`.
   Idempotent: running it twice for the same date is safe (duplicates are
   skipped via `ON CONFLICT DO NOTHING`).
3. The FastAPI backend exposes 8 analytics endpoints (see `docs/design-doc.md`
   §11) plus auth.
4. The React dashboard reads the API and renders the 5 pages defined in the
   design doc.

---

## Database schema

Six tables. The first four are the analytical core; the last two are
operational scaffolding for the POS integration layer (PRD §6). The seventh,
`users`, is for dashboard auth.

```
restaurants    → id, name, city
menu_items     → id, code, name, category, price
bills          → (restaurant_id, bill_no) PK, id UK, sold_at, payment_method, total
bill_items     → id, bill_id FK→bills.id, menu_item_id FK, quantity, unit_price, line_total
pos_connectors → one connector config per restaurant (used by future sync runner)
sync_runs      → execution log (used by future sync runner)
users          → id, username, password_hash, role
```

`bill_items.unit_price` is captured at sale time, so historical revenue stays
accurate even if `menu_items.price` changes later. Revenue metrics always sum
`bill_items.line_total` at the item level and `bills.total` at the bill level
— never profit (no `cost` column in the schema).

Dashboard indexes (added in `01_init.sql`):

```
ix_bills_restaurant_sold     bills(restaurant_id, sold_at)
ix_bill_items_bill           bill_items(bill_id)
ix_bill_items_menu_item      bill_items(menu_item_id)
ix_menu_items_category       menu_items(category)
```

These keep the year-of-data analytical queries inside the design-doc §10.3
performance budget.

---

## API surface (auth required except `/api/auth/login`)

```
POST   /api/auth/login           {username, password}    →  sets `session` cookie
GET    /api/auth/me                                       →  current user
POST   /api/auth/logout                                   →  clears session

GET    /api/restaurants                                   →  filter dropdown
GET    /api/categories                                    →  filter dropdown
GET    /api/best-sellers       ?from&to&restaurants&categories&rank_by&top_n
GET    /api/overview/kpis      ?from&to&restaurants
GET    /api/overview/trend     ?from&to&restaurants
GET    /api/time-series        ?from&to&restaurants&granularity
GET    /api/peak-hours         ?from&to&restaurants
GET    /api/comparison         ?from&to&restaurants

GET    /openapi.json                                      →  for `make types`
GET    /health                                            →  liveness + DB reach
```

All filter params are URL-shaped (CSV: `?restaurants=1,2,5`). Date ranges
> 2 years are rejected with 400 (design-doc §10.7).

---

## CSV format (POS export)

Each row is one line item from a bill, with bill and restaurant fields
repeated — the standard flat shape a POS terminal produces before
normalisation.

```
restaurant_id, restaurant_name, restaurant_city,
bill_no, sold_at, payment_method, bill_total,
item_code, item_name, item_category,
quantity, unit_price, line_total
```

---

## Running the backend without Docker

If you have a local Postgres and want to skip the container:

```bash
cd backend
uv sync
cp ../.env.example ../.env
# edit .env: DB_HOST=localhost, point to your local Postgres
psql -U tortilla_user -d tortilla_db -f ../db/init/01_init.sql
psql -U tortilla_user -d tortilla_db -f ../db/init/02_users.sql

uv run uvicorn app.main:app --reload                # dev server :8000
uv run python -m app.cli generate 2026-05-04
uv run python -m app.cli etl 2026-05-04
```

Same for the frontend:

```bash
cd frontend
pnpm install
pnpm run dev                                        # :5173, proxies to :8000
```

---

## Quality gate

`make check` runs the full read-only quality gate. Use it before every commit.

```bash
make check       # ruff lint + gitleaks secrets scan + pytest (41 tests)
make lint        # ruff format --check + ruff check
make format      # auto-fix formatting + safe lint issues
make secrets     # gitleaks scan (zricethezav/gitleaks via Docker)
make test        # backend pytest suite (41 tests, ~7s)

# Frontend (run from frontend/)
pnpm run lint    # ESLint
pnpm run test    # Vitest (28 tests, <2s)
pnpm exec tsc -b # TypeScript type-check
pnpm run build   # Production build
```

`lint` and `test` run on the host via `uv` for sub-second feedback;
`secrets` runs gitleaks in a one-shot Docker container so no host install is
needed. Ruff config lives in `backend/pyproject.toml` under `[tool.ruff]`.

---

## Documentation

- `docs/PRD.md` — product requirements (V1 scope, schema, milestones)
- `docs/design-doc.md` — analyst dashboard design (wireframes, SQL, API surface)
- `TODOS.md` — deferred work with What/Why/Pros/Cons per item

What's NOT implemented yet, with full context, lives in `TODOS.md`. Highlights:
real POS adapters (M1), sync runner (M2), ops dashboard, admin UI for
connectors, CSV export, production frontend build, CI workflow.
