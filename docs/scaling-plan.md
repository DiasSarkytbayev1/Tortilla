# Scaling Plan — Tortilla → Kafka + Dual-Consumer (OLTP + OLAP) on Azure

Generated 2026-05-11
Branch: main
Target: 1,000+ bills/sec sustained ingest; sub-second dashboard queries over
1+ year of data; hundreds of restaurants.
Context: Harbour.Space Data Storages course / thesis. Cost-aware, demonstrable
in a class demo, not production on-call.

---

## 1. Problem Statement

The current Tortilla stack (FastAPI + sync psycopg2 + single Postgres + CSV
file ETL) was designed for 10 restaurants × 500 bills/day (~5K bills/day total,
PRD §8). The thesis target is **hundreds of restaurants** with **1,000+ bills
per second sustained**, which is ~86M bills/day and ~30B bill-line items per
year. At that volume:

- The single-primary Postgres becomes the analytical bottleneck (full-table
  scans on 30B-row tables, even with indexes, miss the 2s p90 budget).
- CSV-file ETL with per-row `INSERT` (`backend/app/etl/load.py:165-208`) cannot
  keep pace with sustained 1K bills/sec.
- The sync psycopg2 data layer (`backend/app/db.py:8`) opens a fresh TCP
  connection per query, with no pool — port exhaustion happens at ~50 req/sec.
- A single backend container behind no load balancer has no horizontal scale.

This plan migrates the platform to a **dual-consumer Kafka pipeline** with
separate OLTP (Postgres) and OLAP (Azure Data Explorer) stores, hosted on
Azure. Both consumers read from the same Kafka topic; the OLTP store remains
the operational source of truth (audit, refunds, point lookups), and the
OLAP store powers the analyst dashboard at scale.

---

## 2. Constraints

Inherited from the PRD plus thesis-context constraints.

| Constraint | Source | Implication |
|---|---|---|
| Cloud = Azure | Project decision | Prefer managed Azure-native services; minimize self-hosting |
| Course/thesis context | Project decision | Plan must be demoable in a class, not production-on-call; cost discipline matters but uptime SLAs do not |
| Existing schema is the OLTP target | `db/init/01_init.sql` | Postgres schema evolves additively (event_id, voided_at columns); does not break existing tests |
| API contract unchanged | `backend/app/api/*.py`, frontend | The React dashboard sees the same `/api/*` endpoints with identical request/response shapes; the backend swaps the data source per endpoint |
| Bills are append-mostly | PRD §7 | Voids/refunds are modeled as tombstone events, not row deletes |
| `bill_items.unit_price` captured at sale time | PRD §6 | Historical revenue immutable; analytical queries sum line_total, never recompute from menu_items.price |
| Read-only API for analytics | PRD §2 | Dashboard never writes; mutations come only from POS ingest |

---

## 3. Target Architecture

```
                       ┌────────────────────────────────────────────┐
                       │              POS terminals                 │
                       │   (hundreds, different vendors)            │
                       └────────────────────┬───────────────────────┘
                                            │ HTTPS push (per-vendor adapter
                                            │             normalizes payload)
                                            ▼
                       ┌────────────────────────────────────────────┐
                       │   Ingest API  —  FastAPI async + asyncpg   │
                       │   - validates against Schema Registry      │
                       │   - assigns event_id (UUID)                │
                       │   - publishes to Kafka                     │
                       │   N replicas, behind Azure Front Door      │
                       └────────────────────┬───────────────────────┘
                                            │ produce
                                            ▼
                       ┌────────────────────────────────────────────┐
                       │   Azure Event Hubs (Kafka protocol)        │
                       │   topic:    bills.raw                      │
                       │   partition: by restaurant_id (32 parts)   │
                       │   retention: 7 days hot + Capture to Blob  │
                       │              (infinite cold replay)        │
                       └──────────┬─────────────────────┬───────────┘
                                  │                     │
                          consumer group A      consumer group B
                                  │                     │
                  ┌───────────────▼───────────┐  ┌──────▼───────────────────┐
                  │  OLTP consumer            │  │  OLAP ingestion          │
                  │  app/ingest/consumer_pg.py│  │  Event Hubs → ADX direct │
                  │  - dedup by event_id      │  │    data connection       │
                  │  - INSERT bills,bill_items│  │    (managed, no code)    │
                  │  - UPDATE on tombstones   │  │  - dedup by EventId      │
                  │                           │  │  - update policy maps    │
                  │                           │  │    JSON → wide row       │
                  └───────────────┬───────────┘  └──────┬───────────────────┘
                                  │                     │
                                  ▼                     ▼
        ┌────────────────────────────────┐   ┌──────────────────────────────────┐
        │  Azure Database for PostgreSQL │   │  Azure Data Explorer (ADX)       │
        │  Flexible Server               │   │  - Kusto / KQL                   │
        │  - bills, bill_items           │   │  - bill_items_fact (wide,        │
        │    + monthly partitioning      │   │    denormalized, columnar)       │
        │    + event_id, voided_at       │   │  - hot/warm cache tiers          │
        │  - read replica for reports    │   │  - materialized views per KPI    │
        │  - source of truth for audit,  │   │  - tombstone-aware "live" view   │
        │    refunds, point lookups,     │   │                                  │
        │    user/admin operations       │   │                                  │
        └─────────────┬──────────────────┘   └────────────┬─────────────────────┘
                      │                                   │
                      │ ref data + audit lookups          │ analytical queries
                      │                                   │
                      ▼                                   ▼
                  ┌──────────────────────────────────────────────┐
                  │   Analytics API  —  FastAPI async            │
                  │   - /api/auth/*, /api/restaurants,           │
                  │     /api/categories         → Postgres replica│
                  │   - /api/admin/bills/{id}   → Postgres primary│
                  │   - /api/best-sellers, /api/overview/*,      │
                  │     /api/peak-hours, /api/comparison,        │
                  │     /api/time-series        → ADX (KQL)      │
                  │   N replicas behind Azure Front Door         │
                  └──────────────────┬───────────────────────────┘
                                     │
                                     ▼
                  ┌──────────────────────────────────────────────┐
                  │   Azure Cache for Redis                      │
                  │   - hot KPI cache (30-300s TTL)              │
                  │   - reference data cache                     │
                  └──────────────────────────────────────────────┘
                                     ▲
                                     │
                  ┌──────────────────────────────────────────────┐
                  │   React + Vite + shadcn frontend             │
                  │   (unchanged; same /api proxy)               │
                  └──────────────────────────────────────────────┘

   Sidecar: app/ops/reconcile.py — hourly job that compares aggregates
            between PG and ADX, alerts on drift > tolerance

   Hosting: Azure Container Apps for backend containers (KEDA autoscale
            on Event Hubs lag)
```

### Key architectural properties

1. **Kafka is canonical.** Postgres and ADX are both *derived views* of the
   Kafka log. Either can be rebuilt by replaying the topic (or replaying from
   the Event Hubs Capture blob archive for windows older than 7 days).
2. **Idempotent consumers.** Every event carries an `event_id` (UUID, assigned
   by producer). Both consumers dedup by `event_id`. Replay is safe.
3. **Append-only OLAP.** ADX never physically deletes. Voids/refunds are
   *tombstone events* (a new `bill.voided` event with `references_event_id`
   pointing to the original). The OLTP store mutates the row; the OLAP store
   appends and excludes via materialized view. See §7.
4. **Failure isolation.** ADX cluster down → operational endpoints still work
   via Postgres. Postgres primary down → dashboard endpoints still work via
   ADX. The two stores share an input but fail independently.

---

## 4. Component Choices (with Rejected Alternatives)

| Component | Choice | Rejected | Why |
|---|---|---|---|
| Message bus | **Azure Event Hubs (Kafka API)** | Self-hosted Kafka on AKS; Confluent Cloud on Azure | Azure-native, fully managed, speaks Kafka protocol so client code is identical to open-source Kafka, integrates directly with ADX via no-code data connection. Self-hosting Kafka burns 2 weeks of thesis time on ops. Confluent costs ~3× more for marginal extra features. |
| OLAP store | **Azure Data Explorer (ADX / Kusto)** | Azure Synapse dedicated SQL pool; ClickHouse on AKS; Snowflake | Purpose-built for time-series + telemetry, which is exactly the restaurant bills workload. Native Event Hubs ingestion (no consumer code to write). Sub-second queries over billions of rows. Synapse is heavier and BI-oriented. ClickHouse is technically excellent but self-hosting costs more than the thesis is worth. |
| OLTP store | **Azure Database for PostgreSQL Flexible Server** | Cosmos DB; managed Postgres on AKS | Keep the existing schema. Flexible Server gives HA, read replicas, and PITR for free. Cosmos doesn't fit relational audit data. |
| API runtime | **FastAPI async + asyncpg + azure-kusto-data** | Rewrite in Go/Node/Rust | The bottleneck today is sync psycopg2, not Python. Async FastAPI + asyncpg + Kusto SDK serves 5K+ req/sec on a 4-core node. Language rewrite is innovation-token theft. |
| Schema enforcement | **Azure Schema Registry (Event Hubs)** | None; ad-hoc validation | Without producer-side schema validation, bad events drift both stores apart silently. Schema Registry catches it at publish time. |
| Cache | **Azure Cache for Redis** | Memcached; in-process LRU | Boring managed choice on Azure. KPIs change slowly (hourly rollups), so 30-300s TTL is fine. |
| Hosting | **Azure Container Apps** | AKS; App Service | KEDA autoscaling on Event Hubs lag is the *exact* primitive you want for a thesis demo. AKS is appropriate if you also want to demo more ops; either works. |
| Frontend | **No change** | Next.js SSR rewrite | Already shadcn/Vite/React. Frontend is not the bottleneck. |
| Infra-as-code | **Bicep** | Terraform; ARM templates | Azure-native, less verbose than ARM, integrates with CI. Terraform is fine; Bicep is the boring Azure choice. |

---

## 5. Data Model

### 5.1 Postgres schema changes (additive only)

```sql
-- Existing tables unchanged structurally; add columns for event-sourcing
-- and tombstone support.

ALTER TABLE bills
    ADD COLUMN event_id    UUID,
    ADD COLUMN voided_at   TIMESTAMPTZ,
    ADD COLUMN void_reason TEXT,
    ADD COLUMN void_event_id UUID;

-- event_id is the dedup key between Kafka and Postgres
CREATE UNIQUE INDEX ix_bills_event_id ON bills (event_id);

-- Speeds up "live bills only" queries
CREATE INDEX ix_bills_live
    ON bills (restaurant_id, sold_at)
    WHERE voided_at IS NULL;

-- Monthly partitioning on bills (and bill_items by extension)
-- Done as a one-time migration via pg_partman or hand-rolled.
-- Each month becomes a child partition; old partitions can be dropped
-- (or detached and archived) cheaply.
```

### 5.2 ADX schema (denormalized wide row + tombstone column)

```kql
.create table bill_items_fact (
    EventId:            guid,        // dedup key
    EventType:          string,      // 'bill.created' | 'bill.voided'
    ReferencesEventId:  guid,        // for voids: points to original create
    SoldAtUtc:          datetime,
    SoldAtLocal:        datetime,    // precomputed in CHAIN_TZ
    VoidedAtUtc:        datetime,    // null on creates; set on voids
    RestaurantId:       int,
    RestaurantName:     string,      // denormalized at event time
    RestaurantCity:     string,      // denormalized at event time
    BillNo:             string,
    PaymentMethod:      string,
    BillTotal:          decimal,
    MenuItemId:         int,
    MenuItemCode:       string,
    MenuItemName:       string,      // denormalized at event time
    MenuItemCategory:   string,      // denormalized at event time
    Quantity:           int,
    UnitPrice:          decimal,
    LineTotal:          decimal,
    IngestedAtUtc:      datetime     // set by ADX on ingest
)

// Daily partitioning on SoldAtUtc — analog of Postgres monthly partitioning
.alter table bill_items_fact policy partitioning ```
{
  "PartitionKeys": [
    {"ColumnName": "SoldAtUtc", "Kind": "UniformRange",
     "Properties": {"Reference": "2026-01-01", "RangeSize": "1.00:00:00"}}
  ]
}```

// Hot cache: last 30 days on SSD (sub-second over 90M rows)
// Warm cache: 1 year on slower disk
// Cold: blob (still queryable, just slower)
.alter table bill_items_fact policy caching hot = 30d
.alter table bill_items_fact policy retention softdelete = 730d
```

**Denormalization rationale.** Analytical queries over 30B rows cannot afford
joins. We capture the *names* of restaurant/menu_item *at the time of the
event*, accepting that historical rows reflect names as they were when the
sale happened (which is the correct semantic — see PRD §5 design notes on
`bill_items.unit_price` for the same rationale).

### 5.3 Materialized views (the hot dashboard surfaces)

```kql
// "Live bills only" — excludes tombstoned bills, used by most dashboards
.create materialized-view bill_items_live on table bill_items_fact {
    let voided = bill_items_fact
        | where EventType == "bill.voided"
        | distinct ReferencesEventId;
    bill_items_fact
    | where EventType == "bill.created"
    | join kind=leftanti voided on $left.EventId == $right.ReferencesEventId
}

// Daily aggregate per restaurant — drives /api/overview/kpis and trend chart
.create materialized-view revenue_daily on table bill_items_fact {
    bill_items_live
    | summarize Revenue   = sum(LineTotal),
                Bills     = dcount(BillNo),
                ItemsSold = sum(Quantity)
      by RestaurantId, bin(SoldAtLocal, 1d)
}

// Hourly bills per restaurant per DOW — drives /api/peak-hours
.create materialized-view bills_hourly on table bill_items_fact {
    bill_items_live
    | summarize Bills = dcount(BillNo), Revenue = sum(LineTotal)
      by RestaurantId,
         DayOfWeek = dayofweek(SoldAtLocal),
         Hour      = hourofday(SoldAtLocal)
}

// Best sellers daily — drives /api/best-sellers
.create materialized-view best_sellers_daily on table bill_items_fact {
    bill_items_live
    | summarize Qty = sum(Quantity), Revenue = sum(LineTotal)
      by MenuItemId, MenuItemCode, MenuItemName, MenuItemCategory,
         RestaurantId, bin(SoldAtLocal, 1d)
}
```

Materialized views are **incrementally maintained** by ADX — every new event
flips the affected aggregates within seconds. Dashboards query the views, not
the raw fact table.

---

## 6. Consistency Model

The single hardest problem in this architecture. We aim for **eventual
convergence with bounded staleness**, not cross-store linearizability.

### 6.1 What we can and cannot guarantee

| Property | Status | What it means |
|---|---|---|
| Eventual convergence | Achievable | Stop writes, wait, PG and ADX agree |
| Bounded staleness | Achievable | "ADX is never more than 30s behind PG" — measurable, alertable |
| Cross-store linearizability | Not pursued | We do not promise "at wall-clock T, both stores show the same row count" — costs distributed transactions |

For the dashboard workload, eventual + bounded is enough. A user seeing
30s-old sales numbers does not break the business.

### 6.2 The five drift sources and the patterns that prevent each

```
DRIFT SOURCE                              PATTERN

1. Consumer lag skew              →  Monitor Kafka consumer lag,
   (PG faster, ADX slower, etc.)     alert when skew > 60s.
                                     Both consumers expose Prometheus
                                     metrics on offset lag.

2. Different dedup keys           →  Producer assigns event_id (UUID).
                                     PG dedups via UNIQUE(event_id).
                                     ADX dedups via update policy on
                                     EventId. Same key everywhere.

3. Different validation rules     →  Producer-side schema validation.
   (PG rejects, ADX accepts —        Azure Schema Registry enforces
    or vice versa)                   shape at publish time. Bad events
                                     never enter bills.raw — they go
                                     to bills.dead-letter.

4. Different ordering             →  Partition Kafka by restaurant_id.
   assumptions                       Order is guaranteed within a
                                     partition. Events for one
                                     restaurant arrive in send order
                                     at both consumers.

5. Partial consumer failure       →  Idempotent inserts + transactional
   (committed to store but not       offset commits. PG: INSERT ... ON
    to Kafka offset, or vice         CONFLICT (event_id) DO NOTHING.
    versa)                           ADX: dedup by EventId built in.
                                     On restart, replay is safe.
```

### 6.3 Producer-side validation (Pattern 3 detail)

```
POS ─→ Ingest API ─→ [VALIDATE]
                        │
                        ├─ schema OK + business OK ─→ bills.raw
                        │
                        ├─ schema bad (malformed)   ─→ bills.dead-letter
                        │                              + log + 4xx to POS
                        │
                        └─ FK unknown               ─→ bills.dead-letter
                           (unknown restaurant_id,    + alert ops
                            unknown menu_item_id)
```

Validation lives at the **producer**. Both consumers trust the topic and
operate without retry-on-validation logic. A bad event never causes drift
because it never enters the canonical stream.

### 6.4 Reference data consistency

`restaurants` and `menu_items` live in Postgres. The ADX `bill_items_fact`
denormalizes their names. Three policies were considered:

| Approach | Trade-off | Chosen? |
|---|---|---|
| Store only IDs in ADX, join on read | Cleanest; but ADX joins on every dashboard query | No |
| Sync ref data nightly from PG to ADX | One-day staleness on renames; trivial to operate | No |
| Capture names in every event at sale time | Historically correct; rename doesn't retroactively rewrite history | **Yes** |

The third option is **correct, not just convenient**. "What was this item called when it was sold?" is more useful than "what is this item called now?" for chain analytics. It also eliminates the ref-data consistency problem entirely.

### 6.5 Reconciliation job

The job that proves the architecture works.

```python
# app/ops/reconcile.py — runs hourly
def reconcile_hourly(window_start, window_end):
    pg = pg_query("""
        SELECT restaurant_id,
               date_trunc('hour', sold_at) AS h,
               COUNT(*)     AS bills,
               SUM(total)   AS revenue
        FROM bills
        WHERE sold_at >= %s AND sold_at < %s
          AND voided_at IS NULL                  -- exclude tombstoned
        GROUP BY 1, 2
    """, window_start, window_end)

    adx = adx_query("""
        bill_items_live
        | where SoldAtUtc between (datetime(%s) .. datetime(%s))
        | summarize Bills   = dcount(BillNo),
                    Revenue = sum(BillTotal) / dcount(BillNo) * dcount(BillNo)
          by RestaurantId, bin(SoldAtUtc, 1h)
    """, window_start, window_end)

    drift = compare(pg, adx, tolerance_pct=0.1)
    if drift:
        emit_alert(f"PG/ADX drift in {window_start}-{window_end}: {drift}")
        emit_metric("reconcile_drift_count", len(drift))
```

Without this job, drift accumulates invisibly. With it, drift becomes a
visible, actionable signal — and a thesis-defensible artifact ("here is the
chart of PG/ADX agreement over the demo run").

---

## 7. Tombstone Events (Voids and Refunds)

Voids/refunds are mutations from a business perspective, but they fit
*append-only* event sourcing cleanly.

### 7.1 Event flow

```
TIMELINE              KAFKA STREAM (bills.raw)
─────────────────────────────────────────────────────────────────
T = 18:32  sale       event_id = A, type = bill.created,
                       restaurant_id = 3, bill_no = B-12345,
                       total = 18.50, sold_at = 18:32

T = 18:54  refund     event_id = B, type = bill.voided,
                       references_event_id = A,
                       voided_at = 18:54,
                       reason = "customer refund"
```

### 7.2 How each consumer applies the events

| Store | `bill.created` | `bill.voided` |
|---|---|---|
| **Postgres** (mutable) | `INSERT INTO bills (event_id, restaurant_id, ...) ON CONFLICT (event_id) DO NOTHING` | `UPDATE bills SET voided_at = $voided_at, void_reason = $reason, void_event_id = $event_id WHERE event_id = $references_event_id` |
| **ADX** (append-only) | `INSERT INTO bill_items_fact (EventType='bill.created', ...)` | `INSERT INTO bill_items_fact (EventType='bill.voided', ReferencesEventId=$A, VoidedAtUtc=$now)` |

Different physical operations, **same logical truth**: bill A is voided.
Both stores arrive at the same answer to "is bill A live?" when queried.

### 7.3 Why this is the right pattern

| Property | How |
|---|---|
| Audit completeness | The raw `bill_items_fact` keeps *both* the original sale and the void event. "Why was this bill removed? Who voided it? When?" — all answerable. |
| Cheap "deletes" | A void is just an append. Same throughput as a sale. No table rewrite in ADX. |
| Replayability | If void logic has a bug, fix the code and replay Kafka — both stores converge again. Physical deletes cannot be replayed; tombstones can. |
| New business metric for free | "Bills voided this week" becomes a query (`bill_items_fact \| where EventType == 'bill.voided' \| count`) — useful and previously expensive. |

### 7.4 GDPR / legal erasure (the narrow case for physical delete)

"Customer X requests we erase all their data" is a different beast — driven
by legal request, rare (handful per month), and must affect every store
(PG, ADX, Kafka archive, blob). ADX provides `.purge` for exactly this case.
Run as a **separate, audited, manual-approval process**. Do not conflate
with business voids.

Out of scope for the thesis demo — flag for the writeup.

---

## 8. Migration Plan (Phased)

Each phase ships independently. Phases 1-2 alone deliver measurable speedup
on the existing stack with no Azure provisioning required.

| Phase | What ships | Files / new modules | Verification |
|---|---|---|---|
| **0. Provision** | Bicep templates for Event Hubs namespace + topic, ADX cluster (dev tier), Flex PG, Azure Cache for Redis, Container Apps env, Schema Registry. | `infra/` (new) | `az deployment group create` succeeds; resources visible in portal |
| **1. Async DB layer** | Replace psycopg2-binary with **asyncpg** + a pool. Convert all `app/api/*.py` and `app/analytics/sql.py` to async. | `backend/app/db.py`, `app/api/*.py`, `app/analytics/sql.py` | Existing 41 backend tests still pass; p95 latency on `/api/overview/kpis` drops measurably |
| **2. Bulk ETL via COPY** | Rewrite `etl/load.py` to use `COPY` (psycopg2 `copy_expert` or asyncpg `copy_records_to_table`). Keep CSV path for seed/demo. | `backend/app/etl/load.py` | `make seed-1y` runs in <30s (vs minutes today) |
| **3. Schema additions** | `event_id`, `voided_at`, `void_reason`, `void_event_id` columns on `bills`. Monthly partitioning on `bills` (via `pg_partman` or hand-rolled). Tests for tombstone semantics. | `db/init/03_event_sourcing.sql` (new), `backend/tests/test_voids.py` (new) | Existing tests pass; new tests cover void/replay semantics in PG only |
| **4. Kafka producer** | New `app/ingest/api.py` — accepts POS push, validates against Schema Registry, assigns `event_id`, publishes to `bills.raw`. Add Redpanda or Azurite Event Hubs emulator to compose for local dev. | `backend/app/ingest/api.py` (new), `compose.yaml` (add emulator) | k6 load test: 1K msg/sec sustained to local Event Hubs emulator |
| **5. OLTP consumer** | New `app/ingest/consumer_pg.py` — reads `bills.raw`, processes `bill.created` and `bill.voided` events, applies to Postgres idempotently. Deploys as separate Container App scaled by KEDA on Event Hubs lag. | `backend/app/ingest/consumer_pg.py` (new) | Bills land in PG; replay produces no duplicates; voids correctly update `voided_at` |
| **6. OLAP ingestion** | Configure Event Hubs → ADX data connection (declarative, no code). Define `bill_items_fact` table, update policy that denormalizes JSON event into wide row and routes tombstones correctly. | `infra/adx/*.kql` (new) | Bills appear in ADX `bill_items_fact` within 5s of producer publish; voids appear with `EventType='bill.voided'` |
| **7. Analytics rewrite (KQL)** | Port `app/analytics/sql.py` queries to KQL. New `app/analytics/kql.py`. Per-endpoint backend selector (env flag) so we can A/B old vs new at runtime. | `backend/app/analytics/kql.py` (new), `app/api/*.py` (route to `sql` or `kql` per env) | All dashboard pages render identical numbers when backed by PG vs ADX (parity test in §9.1) |
| **8. Materialized views + cache** | Define MVs in ADX (`bill_items_live`, `revenue_daily`, `bills_hourly`, `best_sellers_daily`). Add Redis cache around `/api/overview/kpis` and `/api/peak-hours` (30-300s TTL). | `infra/adx/views.kql`, `backend/app/cache.py` (new) | `/api/overview/kpis` p95 < 200ms over 1-year range |
| **9. Reconciliation + chaos demo** | `app/ops/reconcile.py` hourly job. k6 load script: 1K bills/sec for 10 minutes. Chaos test: kill ADX consumer mid-test; show Kafka retention + automatic recovery on restart. | `backend/app/ops/reconcile.py` (new), `tests/load/` (new) | Demo run sustains 1K bills/sec; drift stays at 0 within tolerance; consumer recovery is automatic |

---

## 9. Test Plan and Benchmark

### 9.1 Coverage map (what gets tested, what is E2E vs eval)

```
CODE PATH COVERAGE — claims that must be tested
═══════════════════════════════════════════════════════════════
[+] Ingest path
    │
    ├── [→E2E] [GAP] POS push → Kafka → both consumers → row visible in
    │          both PG and ADX within 5s
    │
    ├── [GAP] Idempotency in PG: produce same event_id twice → 1 row
    │
    ├── [GAP] Idempotency in ADX: produce same EventId twice → 1 logical
    │         row after dedup update policy
    │
    ├── [GAP] Out-of-order events for same restaurant produce correct
    │         aggregates (ordering is within partition, so this should hold)
    │
    ├── [GAP] Kafka replay: kill ADX consumer, replay 1h of events,
    │         materialized views catch up, drift returns to 0
    │
    └── [GAP] Bad event (malformed JSON, unknown restaurant_id) → routed
              to dead-letter, neither consumer ingests it

[+] Tombstone / void semantics
    │
    ├── [GAP] Publish bill.created then bill.voided → PG row has voided_at
    │         set; ADX bill_items_live excludes the bill
    │
    ├── [GAP] Publish bill.voided BEFORE bill.created (out of order across
    │         restart) → eventual convergence still excludes the bill from
    │         bill_items_live
    │
    └── [GAP] Replay of (created, voided) pair → no spurious un-voiding

[+] Query parity (correctness — old PG queries vs new KQL queries)
    │
    ├── [GAP] [→E2E] For 100 seeded scenarios, /api/overview/kpis returns
    │          identical numbers when backed by PG vs ADX
    │
    ├── [GAP] /api/best-sellers ordering matches between PG and ADX
    │
    ├── [GAP] /api/peak-hours DOW×hour matrix matches between PG and ADX
    │
    └── [GAP] /api/comparison KPI matrix matches (within rounding) between
              PG and ADX

[+] Performance budgets (the thesis claim)
    │
    ├── [GAP] Ingest sustains 1,000 bills/sec for 10 min,
    │         p99 producer→Kafka latency < 50ms
    │
    ├── [GAP] /api/overview/kpis p95 < 200ms over 1-year range
    │         (1B+ rows in ADX)
    │
    ├── [GAP] /api/time-series day-grain, 1-year, all restaurants:
    │         p95 < 800ms
    │
    ├── [GAP] /api/best-sellers top 100, 1-month, all restaurants:
    │         p95 < 500ms
    │
    └── [GAP] /api/peak-hours 1-year, all restaurants: p95 < 600ms

[+] Failure isolation
    │
    ├── [GAP] ADX cluster down (simulated by env flag) → PG-backed
    │         endpoints still return 200; analytics endpoints fail fast
    │         with clear error
    │
    ├── [GAP] PG primary down (failover to replica) → dashboard endpoints
    │         (ADX-backed) still return 200
    │
    └── [GAP] OLTP consumer crashes → OLAP consumer keeps progressing;
              when OLTP consumer restarts, it catches up from last
              committed offset without duplication

[+] Reconciliation
    │
    ├── [GAP] [→E2E] Reconciliation job runs hourly, reports 0 drift
    │          during steady-state load
    │
    └── [GAP] Inject artificial drift (e.g., bypass producer for one
              event) → reconciliation job detects it and emits alert
              within one window

COVERAGE TARGET: every claim above has a test before phase 9 ships.
─────────────────────────────────────────────────────────────────
```

### 9.2 Benchmark shape (the thesis claim)

Two end-to-end runs against identical workloads:

| Run | Stack | Workload | Measured |
|---|---|---|---|
| **Baseline** | Current stack: FastAPI sync + psycopg2 + single Postgres | 1 hour of synthetic POS traffic ramping from 10 to 200 bills/sec | Ingest throughput, ingest p99 latency, dashboard p95 latency per endpoint, error rate |
| **Target** | New stack: FastAPI async + asyncpg + Event Hubs + ADX dual consumer | Same workload, ramping to 1,000+ bills/sec | Same metrics |

Charted side-by-side. Each metric labeled with the architectural change that
moved it. This is the thesis-defensible engineering claim.

### 9.3 Test plan artifact for QA

Affected pages (no UI changes, but data sources change behind the API):
- `/` — Overview (KPIs + trend) → now ADX-backed
- `/best-sellers` → now ADX-backed
- `/time-series` → now ADX-backed
- `/peak-hours` → now ADX-backed
- `/comparison` → now ADX-backed
- `/login`, admin views → still PG-backed

Critical paths:
- Login → Overview → verify all 5 KPIs render and match the seeded data
- Filter change (date range, restaurant) → all pages update in <2s
- Void demo: create a bill via ingest API, then publish a void event → verify it disappears from Overview within reconciliation window

---

## 10. NOT in Scope

| Item | Why deferred |
|---|---|
| Real POS adapters (Lightspeed, Toast, Square) | Mock POS suffices for the thesis. Adapter framework architecture is solid, real vendor breadth is scope creep. |
| Multi-region failover | Single Azure region. Thesis-overkill. |
| Cross-store distributed transactions | We chose eventual consistency. No 2PC, no Saga. Explicit decision, not a gap. |
| Stream processing layer (Flink, kSQLDB) | Event Hubs → ADX update policy handles denormalization. No separate stream processor needed. |
| Real-time customer-facing surfaces | Read-only analyst dashboard per PRD §3. |
| Production cost optimization | Use ADX dev tier, smallest Flex PG B1ms, smallest Container Apps. Document costs but do not optimize. |
| Auth migration | itsdangerous signed cookie is already stateless. Unchanged. |
| GDPR `.purge` workflow | Flagged for thesis writeup as a known follow-up. Not implemented. |
| Real POS push protocol design | Out of scope; assume HTTPS push with shared-secret auth. PRD §5 will specify in future. |
| Per-restaurant timezone display | PRD non-goal; single chain TZ. |

---

## 11. What Already Exists (Reuse, Do Not Rebuild)

| Existing | Where | Reuse for |
|---|---|---|
| `bills`, `bill_items`, `menu_items`, `restaurants` schema | `db/init/01_init.sql` | OLTP layer unchanged structurally. Add `event_id`, `voided_at`, partitioning. |
| Idempotency via `ON CONFLICT DO NOTHING` | `backend/app/etl/load.py:11`, `db/init/01_init.sql:42-44` | Same pattern in Kafka OLTP consumer (`ON CONFLICT (event_id) DO NOTHING`). |
| `pos_connectors`, `sync_runs` tables | `db/init/01_init.sql:61-86` | Repurpose for tracking ingest sources and producer→Kafka publish runs. |
| `app/analytics/sql.py` query catalog | `backend/app/analytics/sql.py` | Reference implementation for KQL parity tests. Keep as `/api?backend=pg` for the benchmark comparison. **Do not delete.** |
| FastAPI route layer | `backend/app/api/*.py` | API contract is unchanged; only the data source per endpoint switches. |
| Date-range validation | `backend/app/validation.py` | Unchanged. Applies to KQL queries the same way. |
| Frontend, auth, FilterBar | `frontend/`, `backend/app/auth/`, `backend/app/api/auth.py` | All unchanged. |
| Existing 41 backend tests + 28 frontend tests | `backend/tests/`, `frontend/src/tests/` | Must still pass after Phase 1 (async) and Phase 7 (KQL). Parity guarantee. |
| Docker Compose | `compose.yaml` | Local dev unchanged; add emulator services for Kafka (Redpanda) and optionally ADX-lite for testing. |

---

## 12. Failure Modes

| Failure | Today (current stack) | New design |
|---|---|---|
| Ingest spike (Black Friday, 5× normal) | PG write storm; backend blocks; dashboard 503s | Event Hubs absorbs; PG and ADX drain at natural rate; dashboard unaffected |
| Postgres primary down | Whole app down | Dashboard endpoints (ADX-backed) keep working; ingest endpoints buffer to Event Hubs; failover to PG replica for OLTP |
| ADX cluster down | N/A | Dashboard endpoints fall back to PG-backed queries via env flag (slower at scale, but available) |
| Bad event (schema violation) | ETL crashes; whole CSV rejected | Dead-letter topic; rest of stream keeps flowing; alert fires |
| Backfill needed (1 month of bills missing) | Manual CSV regenerate + re-ETL | Replay Kafka from offset (or from Event Hubs Capture blob); both consumers re-process idempotently |
| Drift detected between PG and ADX | N/A (only one store today) | Reconciliation job alerts; targeted replay rebuilds the bad window |
| OLTP consumer crashes mid-batch | N/A | Transactional offset commit + idempotent insert; restart catches up with no duplication |
| OLAP consumer falls behind | N/A | KEDA autoscales Container App on Event Hubs lag; alert if lag > 5 min |

**Critical gap (flagged):** if the **producer (Ingest API) is down**, POS terminals get HTTP errors and bills are not captured at all. Mitigations:
- POS adapters retry with backoff (out of scope here; the adapter framework owns this)
- Stand up the producer behind Azure Front Door with N replicas, autoscaled
- Health check + alert on producer error rate
This is the only single point of failure remaining in the design. Flagged for thesis discussion.

---

## 13. Parallelization (Worktrees for Solo Execution)

| Lane | Phases | Module / files | Depends on |
|---|---|---|---|
| **A: API hardening** | 1, 2 | `backend/app/{db,api,analytics,etl}/` | — |
| **B: Infra** | 0, 6, 8 (ADX side) | `infra/`, `infra/adx/` | — |
| **C: Schema** | 3 | `db/init/03_event_sourcing.sql`, `backend/tests/test_voids.py` | A (uses async DB layer) |
| **D: Ingest path** | 4, 5 | `backend/app/ingest/` | B (needs Event Hubs), C (needs schema) |
| **E: Analytics rewrite** | 7, 8 (Redis side) | `backend/app/analytics/kql.py`, `app/cache.py` | B (needs ADX with data) |
| **F: Eval** | 9 | `backend/app/ops/`, `tests/load/` | All others |

**Execution order:**
1. Launch **A** and **B** in parallel worktrees. Both touch independent modules.
2. Once A merges, launch **C** (depends on async DB layer).
3. Once B and C merge, launch **D** in parallel with **E** (D writes events; E reads ADX). They are independent.
4. Once D and E merge, launch **F** (depends on the whole system being up).

**Conflict flags:** Lanes A and D both touch `compose.yaml` (adding service entries) — coordinate sequentially or use careful merge.

---

## 14. Open Questions

1. **Container Apps vs AKS for hosting.** Container Apps wins for thesis demo because KEDA autoscaling on Event Hubs lag is a built-in primitive. AKS demonstrates more ops depth if you want that. Recommend Container Apps.
2. **Schema Registry: JSON Schema vs Avro?** JSON Schema is simpler and human-readable; Avro is compact and well-tooled. For thesis demo, recommend **JSON Schema** (simpler, debuggable in `psql`-equivalent tools).
3. **Reference data sync — at all?** Per §6.4 we capture names in events. But ADX still needs `restaurants` and `menu_items` as small reference tables for *future* queries (e.g., "list all restaurants in Spain" filter dropdown driven by ADX). Recommend: nightly sync of these tables from PG to ADX. Two-line cron job.
4. **Producer authentication for POS push?** Out of scope here. Assume HTTPS + shared-secret per restaurant. The adapter framework owns this; the Ingest API just validates the bearer header.
5. **Bicep vs Terraform.** Bicep is Azure-native, less verbose. Terraform is multi-cloud. For an Azure-only thesis, Bicep is the boring choice.

---

## 15. Success Criteria

V1 of the scaling plan is done when:

- [ ] Ingest API sustains 1,000+ bills/sec for 10 minutes with producer p99 latency < 50ms
- [ ] Both consumers (PG + ADX) drain the stream within 30s of producer publish at steady state
- [ ] All 5 dashboard endpoints render under their performance budgets (§9.1) on the ADX backend over 1 year of seeded data
- [ ] Parity test: 100 seeded scenarios produce identical numbers from PG-backed and ADX-backed endpoints
- [ ] Tombstone (void) event flow works end-to-end: bill appears in dashboard → void event published → bill disappears from dashboard within 60s
- [ ] Reconciliation job reports 0 drift during steady-state load; injected drift is detected within one window
- [ ] Chaos test: kill OLAP consumer mid-load, restart, both stores converge within 5 minutes
- [ ] All 41 existing backend tests still pass on the async DB layer
- [ ] Benchmark chart produced: baseline stack vs target stack, per endpoint, per workload step

---

## 16. Distribution Plan

The system is deployed as Container Apps in a single Azure resource group.
Bicep templates in `infra/` describe the full deployment. CI (GitHub Actions
in `.github/workflows/`) builds container images, pushes to Azure Container
Registry, and triggers Container Apps revisions.

The dashboard is served by the existing API service deployment — internal-only
software accessed at a chain-internal URL after login. No public hosting, no
app stores.

---

## 17. The Assignment (Thesis Execution Order)

Recommended order to maximize chance of a demonstrable result by the
thesis deadline:

1. **Week 1:** Phases 1-2 (async DB, bulk ETL). No Azure provisioning needed.
   Run on existing compose stack. Measure speedup. This already produces
   benchmark data for the "before" half of the thesis claim.
2. **Week 2:** Phase 0 (infra provisioning) + Phase 3 (schema additions).
   Get Azure resources up; start spending Azure credits.
3. **Week 3:** Phases 4-5 (producer + OLTP consumer). End-to-end Kafka
   ingest into Postgres works. The dual-consumer pattern is half-built.
4. **Week 4:** Phase 6 (OLAP ingestion). ADX receives events. Bills appear
   in both stores.
5. **Week 5:** Phase 7 (analytics KQL rewrite) + Phase 8 (materialized
   views + cache). Dashboard now ADX-backed. Run parity tests.
6. **Week 6:** Phase 9 (reconciliation + chaos demo + benchmark). Produce
   the final benchmark chart. Write thesis chapter.

The earliest demoable artifact (end of week 1) is the async speedup — even
if everything else slips, you have evidence of engineering judgment.
