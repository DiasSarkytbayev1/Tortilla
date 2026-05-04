-- =============================================================================
-- init_db.sql
-- Restaurant Chain Analytics Platform — full schema + static seed data
--
-- Run once:  psql -U tortilla_user -d tortilla_db -f init_db.sql
-- Safe to re-run: all CREATE statements use IF NOT EXISTS; seeds use
-- ON CONFLICT DO NOTHING so duplicates are silently skipped.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. CORE ANALYTICAL TABLES
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS restaurants (
    id         SERIAL      PRIMARY KEY,
    name       TEXT        NOT NULL,
    city       TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS menu_items (
    id       SERIAL          PRIMARY KEY,
    code     TEXT            NOT NULL,
    name     TEXT            NOT NULL,
    category TEXT            NOT NULL,
    price    NUMERIC(10, 2)  NOT NULL,
    CONSTRAINT uq_menu_items_code UNIQUE (code)
);

-- Composite PK (restaurant_id, bill_no) — the natural identity of a bill.
-- Surrogate UNIQUE id (bigserial) is the FK target for bill_items.
-- Idempotency: duplicate inserts from overlapping sync windows are absorbed
-- by the PK constraint (ON CONFLICT DO NOTHING in the ETL).
CREATE TABLE IF NOT EXISTS bills (
    restaurant_id  INT            NOT NULL REFERENCES restaurants (id),
    bill_no        TEXT           NOT NULL,
    id             BIGSERIAL      NOT NULL,
    sold_at        TIMESTAMPTZ    NOT NULL,
    payment_method TEXT,
    total          NUMERIC(10, 2) NOT NULL,
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT now(),
    PRIMARY KEY (restaurant_id, bill_no),
    CONSTRAINT uq_bills_id UNIQUE (id)   -- FK anchor for bill_items
);

CREATE TABLE IF NOT EXISTS bill_items (
    id           BIGSERIAL      PRIMARY KEY,
    bill_id      BIGINT         NOT NULL REFERENCES bills (id),
    menu_item_id INT            NOT NULL REFERENCES menu_items (id),
    quantity     INT            NOT NULL CHECK (quantity <> 0),
    unit_price   NUMERIC(10, 2) NOT NULL,
    line_total   NUMERIC(10, 2) NOT NULL
    -- unit_price captured at sale time so historical revenue is immutable
    -- even if menu_items.price changes later.
);

-- ---------------------------------------------------------------------------
-- 2. OPERATIONAL / POS-INTEGRATION TABLES (PRD §6 additions)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pos_connectors (
    id              SERIAL      PRIMARY KEY,
    restaurant_id   INT         NOT NULL REFERENCES restaurants (id),
    pos_type        TEXT        NOT NULL,   -- 'mock_pos', 'lightspeed', 'toast', …
    endpoint_url    TEXT        NOT NULL,
    credentials_ref TEXT        NOT NULL,   -- opaque pointer to secret store
    schedule_cron   TEXT        NOT NULL DEFAULT '0 * * * *',
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    last_synced_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_pos_connectors_restaurant_type UNIQUE (restaurant_id, pos_type)
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id            BIGSERIAL   PRIMARY KEY,
    connector_id  INT         NOT NULL REFERENCES pos_connectors (id),
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    status        TEXT        NOT NULL DEFAULT 'running'
                              CHECK (status IN ('running', 'success', 'failed', 'partial')),
    bills_loaded  INT         NOT NULL DEFAULT 0,
    error_message TEXT,
    window_from   TIMESTAMPTZ,
    window_to     TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- 3. INDEXES (from PRD §8 — sub-second queries on one year of data)
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS ix_bills_restaurant_sold
    ON bills (restaurant_id, sold_at);

CREATE INDEX IF NOT EXISTS ix_bill_items_bill
    ON bill_items (bill_id);

CREATE INDEX IF NOT EXISTS ix_bill_items_menu_item
    ON bill_items (menu_item_id);

CREATE INDEX IF NOT EXISTS ix_sync_runs_connector
    ON sync_runs (connector_id, started_at DESC);

CREATE INDEX IF NOT EXISTS ix_sync_runs_status
    ON sync_runs (status)
    WHERE status <> 'success';

-- ---------------------------------------------------------------------------
-- 4. SEED: RESTAURANTS (static, fixed IDs — never changes between runs)
--
-- IDs 1-10 are used as the canonical restaurant reference throughout the
-- mock CSV generator, ETL, and analytics scripts.  Do not reorder.
-- ---------------------------------------------------------------------------

INSERT INTO restaurants (id, name, city) VALUES
    (1,  'La Tortilla de Oro',    'Madrid'),
    (2,  'El Rincón Tortillero',  'Barcelona'),
    (3,  'Tortillería Valencia',  'Valencia'),
    (4,  'Casa Tortilla Sevilla', 'Sevilla'),
    (5,  'La Tortilla Maña',      'Zaragoza'),
    (6,  'Tortillería del Sur',   'Málaga'),
    (7,  'Tortilla La Huerta',    'Murcia'),
    (8,  'Tortilla Balear',       'Palma'),
    (9,  'Euskal Tortilla',       'Bilbao'),
    (10, 'Tortillería Levante',   'Alicante')
ON CONFLICT (id) DO NOTHING;

-- Keep the serial sequence in sync after explicit ID inserts
SELECT setval(pg_get_serial_sequence('restaurants', 'id'),
              COALESCE((SELECT MAX(id) FROM restaurants), 0) + 1, false);

-- ---------------------------------------------------------------------------
-- 5. SEED: MENU ITEMS (static — same catalog across all restaurants)
-- ---------------------------------------------------------------------------

INSERT INTO menu_items (code, name, category, price) VALUES
    ('TORTILLA_CLASSIC',   'Tortilla Española Clásica', 'tortilla', 8.50),
    ('TORTILLA_ONION',     'Tortilla con Cebolla',      'tortilla', 8.50),
    ('TORTILLA_NO_ONION',  'Tortilla sin Cebolla',      'tortilla', 8.50),
    ('TORTILLA_VEGAN',     'Tortilla Vegana',           'tortilla', 9.00),
    ('TORTILLA_JAMON',     'Tortilla con Jamón',        'tortilla', 10.50),
    ('BREAD',              'Pan Tostado',               'sides',    2.00),
    ('ALIOLI',             'Alioli Casero',             'sides',    1.50),
    ('SALAD_GREEN',        'Ensalada Verde',            'sides',    4.50),
    ('COFFEE',             'Café con Leche',            'drinks',   1.80),
    ('JUICE_OJ',           'Zumo de Naranja Natural',   'drinks',   2.50),
    ('WATER',              'Agua Mineral',              'drinks',   1.20),
    ('BEER',               'Cerveza Caña',              'drinks',   2.80),
    ('WINE_GLASS',         'Vino de la Casa',           'drinks',   3.20),
    ('SOFT_DRINK',         'Refresco',                  'drinks',   2.20)
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 6. SEED: POS CONNECTORS (one mock connector per restaurant)
-- ---------------------------------------------------------------------------

INSERT INTO pos_connectors (restaurant_id, pos_type, endpoint_url, credentials_ref, schedule_cron)
SELECT
    r.id,
    'mock_pos',
    'http://mock-pos.internal/api/v1/restaurant/' || r.id || '/bills',
    'secret/mock_pos/restaurant_' || r.id,
    '0 * * * *'
FROM restaurants r
ON CONFLICT (restaurant_id, pos_type) DO NOTHING;
