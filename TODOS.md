# TODOs

Deferred work, captured during /plan-eng-review on 2026-05-06. Each item has
enough context that someone picking it up in 3 months can start without
re-reading the whole PRD.

---

## pos-adapters — Real POS integration (PRD §F1-F2, M1-M2)

**What:** Replace the mock CSV pipeline with adapter modules that pull bills
from real POS APIs (Toast, Lightspeed, Square as candidates).

**Why:** PRD's defining architectural choice. Without this, the platform is
demo-only — useful as a class project, not as a production system.

**Pros:** Validates the abstraction the rest of the platform rests on.

**Cons:** Requires actual POS API credentials and sandboxes; each vendor is
a 1-2 week effort; vendor APIs change without notice.

**Context:** The current `backend/app/etl/load.py` consumes flat CSV rows.
An adapter would replace `generate.py` with a vendor-specific fetcher that
returns the same internal bill shape. Sync runner (next item) calls the
adapter; loader stays the same.

**Depends on:** Vendor sandbox access, sync-runner.

---

## sync-runner — Scheduler that runs adapters on cron

**What:** APScheduler or similar that wakes up every N minutes per connector,
calls the right adapter, writes a `sync_runs` row.

**Why:** Without this, no real adapter can run unattended. PRD §7 sync flow.

**Pros:** Enables production deployment.

**Cons:** Adds an in-process scheduler thread to the API. For multi-instance
deployment, need leader election (out of scope for V1).

**Context:** `pos_connectors` and `sync_runs` tables already exist in
`db/init/01_init.sql`. Schema is ready. Just need the runner.

**Depends on:** pos-adapters.

---

## ops-dashboard — Connector health view (PRD §F5-F6)

**What:** A new page (or distinct app section) showing per-connector
last-sync status, recent failure history, time-since-last-success.

**Why:** Operations team needs to know when a restaurant's POS connector
is broken, ideally before the analyst notices missing data.

**Pros:** Enables the operations user persona (PRD §3).

**Cons:** Useful only after sync-runner exists.

**Context:** Reuses analyst dashboard's auth + filter bar. Add a new role
`ops` and gate this section to it. Queries `sync_runs` + `pos_connectors`
tables. Wireframes need to be designed (no design doc for this yet).

**Depends on:** pos-adapters, sync-runner.

---

## admin-ui — Connector configuration UI (PRD §F10-F12)

**What:** Forms to add/edit/pause connectors, manage menu catalog, manage
users.

**Why:** PRD §3 admin persona; replaces editing Postgres directly.

**Pros:** Eliminates a class of human-error production incidents.

**Cons:** Needs careful auth (admin role only) and validation.

**Depends on:** pos-adapters (no point configuring connectors if there are no
adapters to back them).

---

## raw-response-storage — Object storage for POS responses (PRD §F14)

**What:** S3 or MinIO bucket where every raw POS API response is stored,
keyed by `(connector_id, sync_run_id, timestamp)`.

**Why:** Allows replaying against new adapter logic without re-fetching from
the source vendor. Critical for diagnosing "why did this bill look weird".

**Pros:** Audit trail; debugging power; PRD §11 risk mitigation.

**Cons:** Adds another piece of infrastructure (MinIO container in compose,
or AWS account).

**Depends on:** pos-adapters.

---

## csv-export — Export buttons on every table (design-doc §10.6)

**What:** `GET /api/export/{best-sellers,time-series,comparison}.csv?...`
that streams CSV using the same SQL the page uses (LIMIT removed). Frontend
"Export" button on every data table.

**Why:** Quality-of-life for analysts who need to share with execs in Excel.

**Pros:** Closes the feature parity gap with Toast/Lightspeed dashboards.

**Cons:** Easy to misuse — capping at 100K rows per design-doc §10.6
prevents accidental year-of-bills exports.

**Context:** Backend pattern: same SQL, stream rows via FastAPI's
`StreamingResponse`. Reuse the existing `tortilla_shops_reports` CSV idea.

---

## auth-rate-limit — Login brute-force protection

**What:** Reject `/api/auth/login` after N failed attempts per IP per minute.

**Why:** Internet-facing login without rate limiting is a known bad pattern.

**Pros:** Stops trivial password guessing.

**Cons:** Requires a counter store (Redis) or in-memory map (single-instance
only).

**Context:** For a class project this is genuinely overkill. Raise priority
the moment this app is deployed somewhere real.

---

## user-mgmt-ui — User management UI (PRD §F13)

**What:** Admin UI to create/disable users, reset passwords, change roles.

**Why:** Today the only path is `psql INSERT`. Doesn't scale past one user.

**Depends on:** admin-ui.

---

## alembic — Database migrations

**What:** Replace the "first-boot init.sql + IF NOT EXISTS" pattern with
proper Alembic migrations.

**Why:** Postgres entrypoint scripts only run on first volume creation. Any
schema change today requires `make reset` which destroys data.

**Pros:** Schema can evolve in production without data loss.

**Cons:** Setup overhead; `IF NOT EXISTS` is enough until the schema actually
needs to change post-deploy.

**Context:** Add `backend/alembic/` and `alembic.ini`. First migration is a
no-op that records the existing schema. Subsequent changes go through
Alembic.

---

## prod-frontend-build — Production build pipeline

**What:** `vite build` produces `frontend/dist/`; FastAPI mounts
`StaticFiles` at `/`; `compose.yaml` profile `prod` swaps the dev-server
service for the build step.

**Why:** Vite dev server is fine for demo, not for prod. Bundle size matters
under real network conditions.

**Pros:** Real deploy story.

**Cons:** Adds a production compose profile and a multi-stage frontend
Dockerfile.

---

## ci-actions — GitHub Actions CI

**What:** `.github/workflows/ci.yml` that runs `make check && make e2e` on
every PR.

**Why:** `make check` is only enforced if the developer runs it. CI
guarantees the gate.

**Pros:** Catches regressions automatically.

**Cons:** Setup and ongoing maintenance.

**Context:** Standard FastAPI + Vite + Postgres setup. Use `services:` for
postgres in the workflow.
