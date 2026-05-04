# Tortilla Restaurant Chain Analytics

A university database systems project (Harbour.Space — Data Storages course).

Simulates a multi-location tortilla restaurant chain where each location's POS terminal exports a flat daily sales file. Those files are loaded into a normalised PostgreSQL database and queried for chain-wide business analytics.

---

## Project Overview

- **10 fixed restaurant locations** across major Spanish cities
- **Mock POS exports** — one flat CSV per restaurant per day, shaped like a real POS terminal output
- **ETL pipeline** — loads flat CSVs into normalised PostgreSQL tables (bills, bill_items, menu_items)
- **Analytical queries** — best sellers, peak hours, and restaurant comparison

---

## Architecture

```
Tortilla/
├── src/
│   ├── install_postgres.sh   # PostgreSQL installation and DB/user creation
│   ├── init_postgres.sh      # Database initialization and Python deps
│   ├── init_db.sql           # One-time DB setup: schema + static seed data
│   ├── generate_mock_csv.py  # Generates daily POS export CSVs
│   ├── etl.py                # Loads CSVs into PostgreSQL
│   └── analytics.py          # Analytical query runner
├── pos_exports/              # Generated daily POS files
│   └── 2026-05-01/
│       ├── restaurant_1.csv
│       ├── restaurant_2.csv
│       └── ...               # One file per restaurant
├── .env                      # DB credentials (not committed)
├── .env.example              # Env template
├── pyproject.toml            # uv project config
└── README.md
```

---

## Data Flow

```
generate_mock_csv.py  →  pos_exports/YYYY-MM-DD/  →  etl.py  →  PostgreSQL  →  analytics.py
     (POS simulation)        (flat CSV files)         (ETL)      (normalised)    (SQL queries)
```

1. `generate_mock_csv.py` produces one flat CSV per restaurant, mimicking a daily POS terminal export — one row per line item, with bill and menu fields denormalised alongside it.
2. `etl.py` reads those CSVs and populates the normalised tables (`menu_items`, `bills`, `bill_items`). Running it multiple times for the same date is safe — duplicates are silently skipped.
3. `analytics.py` runs the three core analytical queries directly against PostgreSQL.

---

## Database Schema

Five tables. The first four are the analytical core; the last two are operational scaffolding for the POS integration layer.

```
restaurants   → id, name, city
menu_items    → id, code, name, category, price
bills         → (restaurant_id, bill_no) PK, id UK, sold_at, payment_method, total
bill_items    → id, bill_id FK→bills.id, menu_item_id FK, quantity, unit_price, line_total
pos_connectors → one connector config per restaurant
sync_runs      → execution log for each scheduled sync
```

`bill_items.unit_price` is captured at sale time, so historical revenue stays accurate even if `menu_items.price` changes later. Revenue metrics always use `SUM(bill_items.line_total)` at the item level and `SUM(bills.total)` at the bill level — never profit (no cost column in the schema).

---

## Setup

### 1. PostgreSQL installation (Ubuntu)

Use the provided installation script:

```bash
# Install PostgreSQL and create database/user
./src/install_postgres.sh
```

Or manually:

```bash
sudo apt update && sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

sudo -u postgres psql <<'SQL'
CREATE USER tortilla_user WITH PASSWORD 'tortilla_pass';
CREATE DATABASE tortilla_db OWNER tortilla_user;
SQL
```

### 2. Python environment (uv)

```bash
uv venv
```

### 3. Config

```bash
cp .env.example .env   # edit DB_PASSWORD if you changed it above
```

### 4. Initialise the database

Use the provided initialization script:

```bash
# Creates all tables, indexes, and seeds restaurants + menu items
./src/init_postgres.sh
```

Or manually:

```bash
uv pip install -r requirements.txt
psql -U tortilla_user -h localhost -d tortilla_db -f init_db.sql
```

---

## Daily workflow

```bash
# 1. Generate mock POS exports for a date
uv run python generate_mock_csv.py 2026-05-01

# 2. Load them into PostgreSQL
uv run python etl.py 2026-05-01

# 3. Run analytics
uv run python analytics.py best_sellers 2026-05-01 2026-05-31
uv run python analytics.py peak_hours   2026-05-01 2026-05-31
uv run python analytics.py comparison   2026-05-01 2026-05-31
```

Running the ETL for a new date **appends** to existing data — it never clears the tables. Running it again for the same date is a no-op (all bills already exist, duplicates are skipped).

---

## Analytical queries

All three map to the core PRD questions.

| Command | Question answered |
|---|---|
| `best_sellers FROM TO` | What's our best-selling dish? |
| `peak_hours FROM TO` | When do we get hammered on Saturdays? |
| `comparison FROM TO` | How does Restaurant A compare to B? |

**Options:**

```bash
# Filter best sellers to one restaurant, show top 5
uv run python analytics.py best_sellers 2026-05-01 2026-05-31 --restaurant_id 2 --top_n 5

# Filter best sellers to one menu category
uv run python analytics.py best_sellers 2026-05-01 2026-05-31 --category tortilla

# Peak hours for a single location
uv run python analytics.py peak_hours 2026-05-01 2026-05-31 --restaurant_id 3
```

---

## CSV format

Each row is one line item from a bill, with bill and restaurant fields repeated — the standard flat shape a POS terminal produces before normalisation.

```
restaurant_id, restaurant_name, restaurant_city,
bill_no, sold_at, payment_method, bill_total,
item_code, item_name, item_category,
quantity, unit_price, line_total
```

---

## Dependencies

```
psycopg2-binary   PostgreSQL driver
pandas            CSV reading and display
faker             Realistic Spanish mock data
python-dotenv     .env config loading
```