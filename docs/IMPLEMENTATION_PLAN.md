# Implementation Plan — Analyst Dashboard (PRD M3)

**Status:** Draft (ready for implementation)
**Owner:** Shamil
**Last updated:** 2026-05-06
**Branch:** DiasS
**Scope source of truth:** `docs/PRD.md` (V1 platform), `docs/design-doc.md` (dashboard design)

---

## 1. Summary

Ship the design-doc.md dashboard end-to-end against the existing data pipeline.
Five pages, eight HTTP endpoints, simple session auth, full test coverage.
Frontend is Vite + React + TypeScript + Tailwind + shadcn/ui + Recharts.

The mock CSV pipeline (`backend/app/etl/`) plays the role of the PRD's adapter
layer. That's fine, the four-table analytical core is identical regardless of
where bills come from. M1 (real adapters), M2 (scheduler + ops dashboard),
and M4 (admin UI for connectors) are explicitly deferred, see §15.

---

## 2. What already exists

| Component | Status | Files |
|---|---|---|
| Postgres schema (PRD §6) | Done | `db/init/01_init.sql` |
| Mock POS exports (proxy for adapters) | Done | `backend/app/etl/generate.py` |
| ETL loader (idempotent) | Done | `backend/app/etl/load.py` |
| 3 analytical SQL queries | Done as CLI | `backend/app/analytics/queries.py` |
| FastAPI scaffold + `/health` | Done | `backend/app/main.py` |
| Docker compose stack | Done | `compose.yaml` |
| Quality gate (ruff + gitleaks + pytest) | Done | `Makefile`, `backend/pyproject.toml` |

---

## 3. Architecture

```
                    ┌──────────────────────────────┐
                    │       Browser (user)         │
                    └──────────────┬───────────────┘
                                   │ HTTPS
                                   ▼
                ┌────────────────────────────────────┐
                │  Vite dev server (frontend:5173)   │
                │  Vite proxy: /api/* → backend:8000 │
                │  React + shadcn + Recharts         │
                └──────────────┬─────────────────────┘
                               │ same-origin (via proxy)
                               ▼
            ┌──────────────────────────────────────────┐
            │  FastAPI (backend:8000)                  │
            │                                          │
            │  /health                                 │
            │  /api/auth/{login,me,logout}             │
            │  /api/restaurants, /api/categories       │
            │  /api/overview/{kpis,trend}              │
            │  /api/best-sellers                       │
            │  /api/time-series                        │
            │  /api/peak-hours                         │
            │  /api/comparison                         │
            │                                          │
            │  SessionMiddleware (signed cookie)       │
            │  APIRouter dependencies = require_user   │
            └──────────────┬───────────────────────────┘
                           │ psycopg2
                           ▼
                    ┌──────────────────┐
                    │  Postgres 16     │
                    │  (db:5432)       │
                    │  init.sql + 4 ix │
                    └──────────────────┘
```

**Boundaries:**
- Frontend never talks to Postgres directly (PRD §5).
- ETL/CLI runs in the same image as the API but on a separate process via
  `docker compose run --rm backend python -m app.cli ...` (already works).
- Auth is a FastAPI dependency mounted at the `/api` router level, so a new
  endpoint cannot accidentally ship without auth.

---

## 4. Stack decisions

| Layer | Choice | Reason |
|---|---|---|
| Frontend bundler | Vite + React 18 + TS | shadcn requires it; matches design-doc.md tech stack |
| Component library | **shadcn/ui** | User pick. Copy-paste components in `frontend/src/components/ui/`, no runtime npm dep for components themselves. |
| Styling | Tailwind CSS | shadcn requires it |
| Charts | Recharts (via shadcn `<ChartContainer>`) | Design-doc.md §5 stack. shadcn ships a chart wrapper that styles Recharts on-brand. |
| Routing | React Router v6 | 5 pages, standard nested routes |
| URL state | `nuqs` or hand-rolled `useSearchParams` | Filter state lives in URL (design-doc §10.1). `nuqs` is typed, declarative, cheap. Recommended. |
| Data fetching | `@tanstack/react-query` | Built-in caching, retry, loading/error states. Maps cleanly to design-doc §10.2 (loading/empty/error). |
| Type sync | **OpenAPI codegen** via `openapi-typescript` | FastAPI emits `/openapi.json`, codegen reads it. One Makefile target (`make types`). Eliminates Pydantic ↔ TS drift. |
| Auth | FastAPI `SessionMiddleware` (`itsdangerous`) | HttpOnly cookie, SameSite=Lax, secure-in-prod. PRD §F13 says "auth required", that's all. |
| Test (backend) | pytest (already in place) | |
| Test (frontend unit) | Vitest + Testing Library | Vite-native |
| Test (E2E) | Playwright, 3 critical paths | User confirmed above |

---

## 5. Directory layout (new + changed)

```
backend/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py              # NEW — CommonFilters, require_user, get_db
│   │   ├── auth.py              # NEW — login, me, logout
│   │   ├── meta.py              # NEW — /restaurants, /categories
│   │   ├── overview.py          # NEW — /overview/kpis, /overview/trend
│   │   ├── best_sellers.py      # NEW
│   │   ├── time_series.py       # NEW
│   │   ├── peak_hours.py        # NEW
│   │   ├── comparison.py        # NEW
│   │   └── router.py            # NEW — composes the /api APIRouter
│   ├── analytics/
│   │   ├── queries.py           # CHANGED — keep CLI-friendly print+return
│   │   └── sql.py               # NEW — pure data, no print, returns dicts
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── passwords.py         # NEW — bcrypt hash/verify
│   │   └── users.py             # NEW — get_user_by_username, etc.
│   ├── validation.py            # NEW — parse_date_range, common 400s
│   ├── config.py                # CHANGED — add SECRET_KEY, SESSION_TTL_S
│   └── main.py                  # CHANGED — add SessionMiddleware, mount router
└── tests/
    ├── conftest.py              # NEW — db fixture, auth fixture
    ├── test_auth.py             # NEW
    ├── test_meta.py             # NEW
    ├── test_overview.py         # NEW
    ├── test_best_sellers.py     # NEW
    ├── test_time_series.py      # NEW
    ├── test_peak_hours.py       # NEW
    ├── test_comparison.py       # NEW
    └── test_validation.py       # NEW

db/init/
├── 01_init.sql                  # CHANGED — add 4 indexes (design-doc §10.4)
└── 02_users.sql                 # NEW — users table + dev seed user

frontend/                         # NEW everything below
├── package.json
├── vite.config.ts                # proxy /api → backend:8000
├── tsconfig.json
├── tailwind.config.ts
├── components.json               # shadcn config
├── Dockerfile
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx                   # router + AuthProvider + QueryClient
    ├── api/
    │   ├── client.ts             # fetch wrapper using openapi-fetch
    │   └── types.ts              # generated by `make types`
    ├── auth/
    │   ├── AuthProvider.tsx
    │   ├── useAuth.ts
    │   └── ProtectedRoute.tsx
    ├── components/
    │   ├── ui/                   # shadcn components live here
    │   ├── FilterBar.tsx
    │   ├── KPICard.tsx
    │   ├── RevenueLineChart.tsx
    │   ├── RankedBarChart.tsx
    │   ├── DOWHourHeatmap.tsx
    │   └── ChartShell.tsx        # loading/empty/error wrapper
    ├── hooks/
    │   ├── useFilters.ts         # URL state via nuqs
    │   └── usePreviousPeriod.ts
    ├── lib/
    │   ├── format.ts             # currency, dates, percentages
    │   └── periods.ts            # last 7d, MTD, etc.
    ├── pages/
    │   ├── Login.tsx
    │   ├── Layout.tsx            # nav + global filter bar
    │   ├── Overview.tsx
    │   ├── BestSellers.tsx
    │   ├── TimeSeries.tsx
    │   ├── PeakHours.tsx
    │   └── Comparison.tsx
    └── tests/
        ├── FilterBar.test.tsx
        ├── KPICard.test.tsx
        ├── *.test.tsx (one per chart wrapper, one per page)
        └── e2e/
            ├── auth.spec.ts
            ├── filter-url.spec.ts
            └── best-sellers.spec.ts
```

---

## 6. Phased work breakdown

### Phase 0: Migration prep (~30 min CC)

Goal: schema is ready for the dashboard. Existing `make up` data still works.

1. Append to `db/init/01_init.sql` the 4 indexes from design-doc §10.4:
   ```sql
   CREATE INDEX IF NOT EXISTS ix_bills_restaurant_sold_at
     ON bills (restaurant_id, sold_at);
   CREATE INDEX IF NOT EXISTS ix_bill_items_bill_id
     ON bill_items (bill_id);
   CREATE INDEX IF NOT EXISTS ix_bill_items_menu_item_id
     ON bill_items (menu_item_id);
   CREATE INDEX IF NOT EXISTS ix_menu_items_category
     ON menu_items (category);
   ```
2. Create `db/init/02_users.sql`:
   ```sql
   CREATE TABLE IF NOT EXISTS users (
       id            SERIAL PRIMARY KEY,
       username      TEXT UNIQUE NOT NULL,
       password_hash TEXT NOT NULL,
       role          TEXT NOT NULL DEFAULT 'analyst',
       created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
   );
   -- bcrypt of 'devpass' — change for prod via /api/admin/users (M4)
   INSERT INTO users (username, password_hash, role)
   VALUES ('dev', '$2b$12$<bcrypted-devpass>', 'analyst')
   ON CONFLICT (username) DO NOTHING;
   ```
3. `make reset && make up` to verify init runs cleanly.
4. Seed 90 days of mock data: a small loop in `make seed-90d` that calls
   generate + etl for each date. Used for perf verification next step.
5. Run `EXPLAIN (ANALYZE, BUFFERS)` on the year-data version of the heaviest
   queries (Time Series day-grain + Comparison CTE + Best Sellers). Confirm
   no sequential scans on `bills`. **Add this output to the plan as a comment
   block**, so future regressions are visible.

**Acceptance:** `make reset && make up` clean, 90 days of seed data loaded, all
EXPLAIN plans use the indexes.

### Phase 1: Backend refactor (~30 min CC) — parallel with Phase 4

Goal: separate pure SQL from CLI display so endpoints can reuse it.

1. Create `backend/app/analytics/sql.py`:
   - `best_sellers_rows(...)` — same SQL, no print, returns `list[dict]`
   - `peak_hours_rows(...)`, `comparison_rows(...)`, plus the new endpoints'
     SQL functions: `overview_kpis_rows`, `overview_trend_rows`,
     `time_series_rows`, etc. Verbatim from design-doc §9.
2. `backend/app/analytics/queries.py` keeps its print-and-return wrappers,
   each one delegates to the matching `sql.py` function. The CLI keeps
   working.
3. Create `backend/app/validation.py` with `parse_date_range(from_, to_)`:
   - `from > to` → 400
   - `to - from > 730 days` → 400 (design-doc §10.7)
   - Bad ISO format → 400
4. Update `backend/tests/test_imports.py` to include the new modules.

**Acceptance:** `make check` clean. Existing CLI commands unchanged.

### Phase 2: Backend — auth + 3 endpoints (~45 min CC)

Goal: a logged-in user can fetch the smallest endpoint set.

1. `backend/app/auth/passwords.py`: bcrypt verify (`passlib[bcrypt]` to deps).
2. `backend/app/auth/users.py`: `get_user_by_username`, `verify_password`.
3. `backend/app/api/auth.py`:
   - `POST /api/auth/login {username, password}` — sets session cookie.
   - `GET /api/auth/me` — returns the current user `{id, username, role}`.
   - `POST /api/auth/logout` — clears the session.
4. `backend/app/api/deps.py`:
   - `require_user` dependency, raises 401 if no/invalid session.
   - `CommonFilters` dependency — parses `from`, `to`, `restaurants`,
     `categories` from query params, validates them, returns a typed model.
5. `backend/app/api/router.py`:
   ```python
   api = APIRouter(prefix="/api", dependencies=[Depends(require_user)])
   api_public = APIRouter(prefix="/api")
   api_public.include_router(auth_router)   # login is the one public route
   api.include_router(meta_router)
   ```
6. `backend/app/api/meta.py`: `/api/restaurants`, `/api/categories`.
7. `backend/app/api/best_sellers.py`: wires `sql.best_sellers_rows`.
8. `backend/app/main.py`: add `SessionMiddleware`, mount both routers.
9. `backend/app/config.py`: add `SECRET_KEY` (env), `SESSION_TTL_S=86400`.
10. `.env.example`: add `SECRET_KEY=change-me-in-prod-only-dev`.
11. Tests for everything above (see Phase 7).

**Acceptance:** `curl -c jar.txt -X POST -d '{"username":"dev","password":"devpass"}' http://localhost:8000/api/auth/login`,
then `curl -b jar.txt http://localhost:8000/api/best-sellers?from=2026-04-01&to=2026-04-30`
returns JSON.

### Phase 3: Backend — remaining 5 endpoints (~30 min CC)

Build out per design-doc §11:
- `GET /api/overview/kpis` — 5 KPIs + previous-period deltas (design-doc §9.1)
- `GET /api/overview/trend` — daily revenue series
- `GET /api/time-series` — bucketed series, granularity param
- `GET /api/peak-hours` — DOW × hour matrix in CHAIN_TZ
- `GET /api/comparison` — CTE-based per-restaurant KPIs (§9.5)

All endpoints depend on `CommonFilters`. Pure data, no formatting.

**Acceptance:** all 8 endpoints return valid JSON for a logged-in user; 401
for an unauthenticated request to anything but `/api/auth/login`.

### Phase 4: Frontend scaffold (~45 min CC) — parallel with Phase 1

Goal: `make up` brings up frontend at :5173 with shadcn baseline.

1. `cd frontend && npm create vite@latest . -- --template react-ts`
2. Install Tailwind: follow shadcn's exact instructions for Vite + Tailwind v4
   (one tailwind.css file, one Vite plugin).
3. `npx shadcn@latest init` — picks `default` theme, slate color, css variables.
4. Add shadcn components used by the dashboard:
   ```
   button card input label sheet table tabs select dropdown-menu
   skeleton tooltip popover toast badge separator dialog
   ```
   Plus the chart components: `npx shadcn@latest add chart`.
5. Install runtime deps:
   ```
   react-router-dom @tanstack/react-query nuqs openapi-fetch zod
   recharts class-variance-authority clsx tailwind-merge lucide-react
   ```
6. Configure `vite.config.ts` proxy:
   ```ts
   server: {
     proxy: { '/api': 'http://backend:8000', '/openapi.json': 'http://backend:8000' }
   }
   ```
7. `frontend/Dockerfile` (dev image, Node 22 alpine) + add `frontend` service
   to `compose.yaml`:
   ```yaml
   frontend:
     build: ./frontend
     volumes:
       - ./frontend:/app
       - /app/node_modules
     ports: ["5173:5173"]
     command: npm run dev -- --host 0.0.0.0
     depends_on: [backend]
   ```
8. `Makefile`: add `make types` target that runs
   `npx openapi-typescript http://localhost:8000/openapi.json -o frontend/src/api/types.ts`.
9. Add `frontend` lint target: `cd frontend && npm run lint` plus extend
   `make check` to call it.

**Acceptance:** `make up` brings up all three services. Browsing
`http://localhost:5173` shows a default Vite + shadcn page.

### Phase 5: Frontend — Auth + Best Sellers (~60 min CC)

Goal: end-to-end vertical slice through one page.

1. `make types` to generate `frontend/src/api/types.ts`.
2. `src/api/client.ts` — `openapi-fetch` instance pointing at `/api`,
   credentials: `include` so cookies round-trip.
3. `src/auth/AuthProvider.tsx` — checks `/api/auth/me` on mount, exposes
   `{user, login, logout}`.
4. `src/auth/ProtectedRoute.tsx` — redirects to `/login` if not auth'd.
5. `src/pages/Login.tsx` — shadcn `Card` + `Input` + `Button`, calls
   `/api/auth/login`. Shows error on 401.
6. `src/pages/Layout.tsx` — top nav (5 page links via shadcn `Tabs`-style)
   + global `<FilterBar>` + `<Outlet>`.
7. `src/components/FilterBar.tsx` — date range picker (shadcn `Calendar` +
   `Popover`), restaurant multi-select (`Sheet`), category multi-select. URL
   sync via `nuqs`. Greys out filters not applicable to the current page
   (design-doc §8 filter applicability matrix).
8. `src/components/KPICard.tsx` — value + delta indicator + tooltip.
9. `src/components/ChartShell.tsx` — wraps any chart with shadcn skeleton
   (loading), empty state, error state with retry.
10. `src/pages/BestSellers.tsx` — full page per design-doc §9.2. Uses
    react-query against `/api/best-sellers`. Renders shadcn `Table` + the
    ranked horizontal bar chart via shadcn's chart wrapper.

**Acceptance:** Login → land on `/`. Click "Best Sellers" → see real data
from `make seed-90d`. Change rank-by toggle → table re-sorts.

### Phase 6: Frontend — remaining 4 pages (~90 min CC)

In order:
1. `Overview` — 5 KPI cards + revenue trend line. Uses `usePreviousPeriod`
   hook to fetch the prior-period KPIs in parallel.
2. `TimeSeries` — granularity radio group + metric radio + previous-period
   overlay checkbox. Reuses `RevenueLineChart`.
3. `PeakHours` — `DOWHourHeatmap` (custom 7×24 SVG with `<rect>` per cell,
   continuous colour scale) + Hourly Bars view via shadcn chart.
4. `Comparison` — KPI matrix shadcn `Table` (highest = green tint,
   lowest = red tint per row) + ranked horizontal bars + overlaid line chart.

**Acceptance:** All 5 pages load real data. Filter bar persists across
page navigation.

### Phase 7: E2E + verification (~45 min CC)

1. `npm install -D @playwright/test && npx playwright install --with-deps chromium`
2. Three specs (per the test review diagram).
3. Add `make e2e` target running Playwright against `make up` stack.
4. Re-run all `EXPLAIN (ANALYZE)` queries on the seeded year of data,
   record p90 timings in `docs/perf-baseline.md`.
5. Bundle check: `npm run build` → `du -sh dist/` → must be < 1MB total.
6. Update root `README.md` quickstart with the new flow:
   ```
   make up
   open http://localhost:5173
   # log in as dev / devpass
   ```

**Acceptance:** `make check && make e2e` both green. Perf baseline written.

---

## 7. Implementation order with parallelization

```
Sequential first:
  Phase 0 (schema + indexes + seed-90d)

Parallel lanes after Phase 0:
  Lane A (Backend): Phase 1 → Phase 2 → Phase 3
  Lane B (Frontend scaffold): Phase 4

Sequential after both lanes:
  Phase 5 (vertical slice — needs Phase 3 done) → Phase 6 → Phase 7
```

**Conflict flags:** none. Lane A touches `backend/app/`, Lane B touches
`frontend/`. Compose.yaml is touched in Phase 4 only.

---

## 8. Test coverage commitments

- **Backend (pytest):** 31 tests across the 8 endpoints + auth + validation.
  Every endpoint has happy path + at least one edge case (empty result,
  invalid filter, tie-break stability where applicable).
- **Frontend unit (Vitest):** 12 tests covering FilterBar URL round-trip,
  KPICard rendering + delta arrow direction, chart wrappers, page-level
  loading/empty/error states.
- **E2E (Playwright):** 3 critical paths — auth flow, filter URL persistence
  across reload, Best Sellers rank-by toggle.

Tests are written **alongside** the feature code in each phase, not deferred.
`make check` runs ruff + gitleaks + pytest + frontend lint. `make e2e`
is a separate target so the tight loop stays sub-second.

---

## 9. Failure modes and mitigations

| Codepath | Failure | Mitigation |
|---|---|---|
| `/api/auth/login` | Brute force | TODO for prod (rate limit). Class project: not blocking. |
| `/api/*` | DB unreachable | FastAPI 500 → react-query retry → ChartShell error state. Per-panel isolation per design-doc §10.8. |
| `/api/time-series` 1y range | Query > 2s | Phase 0 EXPLAIN check catches this before Phase 6. |
| `/api/comparison` 6 restaurants | CTE seq scan | Same — verified in Phase 0. |
| Filter URL malformed | `r=` or `from > to` | `parse_date_range` returns 400; FilterBar zod-validates before sending. |
| Session cookie tampered | Forged session id | `SessionMiddleware` signs with `SECRET_KEY`; tamper → invalid → 401. |
| Cross-DST time series query | Bills mis-bucketed | Phase 3 + test_time_series.py:dst covers a range crossing DST. |
| Postgres entrypoint | Init only runs on first volume creation | README documents `make reset` (already noted in §6 Phase 0). |

**Critical gaps** (silent failure with no test or handling): **none**. All
listed failures either have a test or a clear user-visible error path.

---

## 10. Performance budgets (from design-doc §10.3)

| View | p90 query budget |
|---|---|
| Overview KPI (each) | 200 ms |
| Overview trend | 400 ms |
| Best Sellers (Top 100) | 500 ms |
| Time Series (year, day) | 800 ms |
| Peak Hours heatmap (year) | 600 ms |
| Comparison (6 restaurants, year) | 1,200 ms |
| Whole page (network + render) | < 2 s |

If any budget misses on the seeded year of data, the next move is a
daily-rollup table refreshed by an in-process scheduler. **TODO** if needed.

---

## 11. Auth details

- Cookie name: `session`. `HttpOnly`, `SameSite=Lax`, `Secure` when
  `ENV=production`.
- TTL: 24 hours (`SESSION_TTL_S=86400`).
- Signed via `SECRET_KEY` env (must be set, no insecure default — startup
  asserts).
- One default user from seed: `dev` / `devpass`. README documents how to
  create more via psql `INSERT` for now.
- Logout clears the cookie server-side and client-side.

---

## 12. Data seeding for dev

`make seed-90d` runs the existing generator + ETL for 90 dates ending today.
Adds ~450K rows total. Used for visual smoke and EXPLAIN verification.

`make seed-1y` — same but 365 dates. Used for performance budget verification.

These are make targets that loop:
```makefile
seed-90d:
	for i in $$(seq 0 89); do \
	    DATE=$$(date -u -v-$${i}d +%Y-%m-%d 2>/dev/null || date -u -d "$$i days ago" +%Y-%m-%d); \
	    docker compose run --rm backend python -m app.cli generate $$DATE; \
	    docker compose run --rm backend python -m app.cli etl $$DATE; \
	done
```

---

## 13. Acceptance criteria (definition of done)

- [ ] All 8 endpoints return valid JSON; auth gates everything except `/api/auth/login`.
- [ ] All 5 pages render real data from a 90-day seeded DB.
- [ ] FilterBar state persists across pages and reloads (URL is the source).
- [ ] Loading / empty / error states implemented on every chart and table (design-doc §10.2).
- [ ] `make check` green: ruff, gitleaks, pytest, frontend lint.
- [ ] `make e2e` green: 3 Playwright specs.
- [ ] All p90 query budgets met against `make seed-1y` (Phase 7).
- [ ] No page crashes whole-app on a single API failure.
- [ ] Default session cookie config: HttpOnly + SameSite=Lax + Secure-in-prod.
- [ ] Bundle < 1MB total (Phase 7 check).

---

## 14. NOT in scope (deferred to TODOS.md)

| Item | Why deferred | TODO key |
|---|---|---|
| Real POS adapters (PRD §F1-F2) | No real vendor APIs to integrate against | `pos-adapters` |
| Sync runner / scheduler (PRD §F3-F6) | Mock CSV pipeline already covers the academic interest | `sync-runner` |
| Operational dashboard (PRD §F5-F6) | Connector health UI requires real connectors | `ops-dashboard` |
| Admin UI for connectors (PRD §F10-F12) | Same as above | `admin-ui` |
| Object storage for raw POS responses (PRD §F14) | Not needed for mock pipeline | `raw-response-storage` |
| CSV export endpoints (design-doc §10.6) | Explicitly deferrable per design doc; do later if time | `csv-export` |
| Auth: rate limiting on /login | Class project, no traffic | `auth-rate-limit` |
| Auth: password reset / user mgmt UI | Same | `user-mgmt-ui` |
| Multi-currency (PRD §2 non-goal) | Not in V1 | — |
| Alembic migrations | init.sql + IF NOT EXISTS is enough for V1 | `alembic` |
| Production frontend build (`vite build` → static via FastAPI/nginx) | Dev server is enough for class demo | `prod-frontend-build` |
| CI workflow (GitHub Actions) | Local make check is enough; add later | `ci-actions` |
| Native mobile (PRD §2 non-goal) | — | — |

---

## 15. Open questions to resolve during implementation

These are minor and can be settled inline by the engineer doing the work:

1. **Day-of-week first row order:** Postgres `EXTRACT(DOW)` returns 0=Sun.
   Frontend reorders to Mon-first. Confirmed in design-doc §10 open question 2.
2. **shadcn theme colors:** picks `slate` by default. Override only if the
   chain has a brand. Class project: stick with default.
3. **Date range picker UX:** shadcn `Calendar` is a single picker. For range,
   compose two or use `react-day-picker` mode="range". Pick whichever ships
   first.
4. **What happens when seeding 1y of data on a laptop?** Generator + ETL
   takes ~2 min on a modern machine. If too slow, lower `seed-1y` to 6 months.

---

## 16. Source-of-truth pointers

- **Schema:** `db/init/01_init.sql` (and `02_users.sql` after Phase 0)
- **SQL queries:** all in `backend/app/analytics/sql.py` — design-doc §9 is
  the original spec
- **Wireframes:** `docs/design-doc.md` §9
- **API surface:** `docs/design-doc.md` §11 (8 endpoints, this plan adds the
  3 auth endpoints)
- **Filter behavior:** `docs/design-doc.md` §8, §10.1
- **Empty/loading/error states:** `docs/design-doc.md` §10.2
- **Performance budgets:** `docs/design-doc.md` §10.3 (mirrored in §10 above)

When the design doc and this plan disagree, the design doc wins for *what*
ships, this plan wins for *how* it's structured.
