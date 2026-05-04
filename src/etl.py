"""
etl.py
──────
One-function ETL that reads flat POS export CSVs for a given date and
populates the normalised PostgreSQL tables:

    menu_items   ← upserted from the item_code/name/category/unit_price columns
    bills        ← upserted using (restaurant_id, bill_no) composite PK
    bill_items   ← inserted only for bills that were newly created this run

Idempotency guarantee
---------------------
Running the ETL twice for the same date is safe.
  • menu_items:  ON CONFLICT (code) DO NOTHING
  • bills:       ON CONFLICT (restaurant_id, bill_no) DO NOTHING — duplicate
                 CSVs (e.g. overlapping sync windows) are silently skipped.
  • bill_items:  only inserted when the parent bill was just inserted.
                 This prevents orphaned or doubled line items.

Usage
-----
    python etl.py                    # loads today's exports
    python etl.py 2026-05-01         # loads a specific date
    python etl.py 2026-05-01 ./data  # custom exports root directory

Or call programmatically:
    from etl import run_etl
    run_etl("2026-05-01")
"""

import os
import sys
from datetime import datetime, timezone

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "tortilla_db"),
        user=os.getenv("DB_USER", "tortilla_user"),
        password=os.getenv("DB_PASSWORD", "tortilla_pass"),
    )


# ---------------------------------------------------------------------------
# SQL statements
# ---------------------------------------------------------------------------

UPSERT_MENU_ITEM = """
    INSERT INTO menu_items (code, name, category, price)
    VALUES (%(code)s, %(name)s, %(category)s, %(price)s)
    ON CONFLICT (code) DO NOTHING
    RETURNING id, code
"""

# Returns the bill's surrogate id only when newly inserted.
# If it was already there, returns nothing (DO NOTHING skips RETURNING).
INSERT_BILL = """
    INSERT INTO bills (restaurant_id, bill_no, sold_at, payment_method, total)
    VALUES (%(restaurant_id)s, %(bill_no)s, %(sold_at)s, %(payment_method)s, %(total)s)
    ON CONFLICT (restaurant_id, bill_no) DO NOTHING
    RETURNING id, restaurant_id, bill_no
"""

INSERT_BILL_ITEM = """
    INSERT INTO bill_items (bill_id, menu_item_id, quantity, unit_price, line_total)
    VALUES (%(bill_id)s, %(menu_item_id)s, %(quantity)s, %(unit_price)s, %(line_total)s)
"""

# Fetch the surrogate id for a bill we know exists (for idempotency check)
SELECT_BILL_ID = """
    SELECT id FROM bills WHERE restaurant_id = %(restaurant_id)s AND bill_no = %(bill_no)s
"""


# ---------------------------------------------------------------------------
# Core ETL function
# ---------------------------------------------------------------------------

def run_etl(report_date: str | None = None, exports_root: str = "pos_exports") -> dict:
    """
    Load all restaurant POS export CSVs for *report_date* into PostgreSQL.

    Parameters
    ----------
    report_date : str, optional
        Date in YYYY-MM-DD format.  Defaults to today (UTC).
    exports_root : str
        Root directory that holds date-partitioned subdirectories.
        Default: ``pos_exports/`` (output of generate_mock_csv.py).

    Returns
    -------
    dict
        Summary stats: bills_inserted, items_inserted, bills_skipped.
    """
    # ── Resolve date ──────────────────────────────────────────────────────
    if report_date:
        try:
            datetime.strptime(report_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"report_date must be YYYY-MM-DD, got: {report_date!r}")
        date_str = report_date
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    date_path = os.path.join(exports_root, date_str)
    if not os.path.isdir(date_path):
        raise FileNotFoundError(
            f"No exports directory found at {date_path!r}. "
            "Run generate_mock_csv.py first."
        )

    csv_files = sorted(
        f for f in os.listdir(date_path) if f.endswith(".csv")
    )
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {date_path!r}.")

    print(f"\n{'='*60}")
    print(f"  ETL run — {date_str}  ({len(csv_files)} files)")
    print(f"{'='*60}")

    # ── Connect ───────────────────────────────────────────────────────────
    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    stats = {"bills_inserted": 0, "items_inserted": 0, "bills_skipped": 0}

    try:
        # ── Step 1: build/refresh in-memory menu_item code → id map ──────
        menu_id_map: dict[str, int] = {}

        for csv_file in csv_files:
            df = pd.read_csv(os.path.join(date_path, csv_file))
            _upsert_menu_items(cur, df, menu_id_map)

        conn.commit()
        print(f"[1/3] menu_items: {len(menu_id_map)} items in catalog")

        # ── Step 2 & 3: bills + bill_items, one file at a time ────────────
        for csv_file in csv_files:
            df = pd.read_csv(os.path.join(date_path, csv_file))
            file_stats = _load_bills_and_items(cur, df, menu_id_map)

            stats["bills_inserted"] += file_stats["bills_inserted"]
            stats["items_inserted"] += file_stats["items_inserted"]
            stats["bills_skipped"]  += file_stats["bills_skipped"]

            conn.commit()
            print(
                f"  {csv_file:<30}  "
                f"bills +{file_stats['bills_inserted']:>4} "
                f"(skip {file_stats['bills_skipped']:>4})  "
                f"items +{file_stats['items_inserted']:>5}"
            )

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    print(f"\n[DONE] bills inserted: {stats['bills_inserted']:,}  "
          f"skipped: {stats['bills_skipped']:,}  "
          f"bill_items inserted: {stats['items_inserted']:,}")
    return stats


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _upsert_menu_items(cur, df: pd.DataFrame, menu_id_map: dict) -> None:
    """
    Upsert every unique item_code found in this file into menu_items.
    Populates menu_id_map with code → database id for use in bill_items.
    """
    unique_items = (
        df[["item_code", "item_name", "item_category", "unit_price"]]
        .drop_duplicates("item_code")
    )

    for _, row in unique_items.iterrows():
        code = row["item_code"]
        if code in menu_id_map:
            continue

        cur.execute(UPSERT_MENU_ITEM, {
            "code":     code,
            "name":     row["item_name"],
            "category": row["item_category"],
            "price":    float(row["unit_price"]),
        })
        result = cur.fetchone()

        if result:
            # Newly inserted → id returned
            menu_id_map[code] = result[0]
        else:
            # Already existed → fetch id
            cur.execute("SELECT id FROM menu_items WHERE code = %s", (code,))
            menu_id_map[code] = cur.fetchone()[0]


def _load_bills_and_items(
    cur, df: pd.DataFrame, menu_id_map: dict
) -> dict:
    """
    For each unique bill in the dataframe:
      1. Try to insert the bill.
      2. If newly inserted, insert all its bill_items.
      3. If it already existed, skip (idempotent).
    """
    stats = {"bills_inserted": 0, "bills_skipped": 0, "items_inserted": 0}

    # Group rows by bill_no so we process one bill at a time
    for bill_no, group in df.groupby("bill_no"):
        first = group.iloc[0]

        cur.execute(INSERT_BILL, {
            "restaurant_id": int(first["restaurant_id"]),
            "bill_no":       bill_no,
            "sold_at":       first["sold_at"],
            "payment_method": first["payment_method"],
            "total":         float(first["bill_total"]),
        })
        row = cur.fetchone()

        if row is None:
            # Bill already exists — skip all its items too
            stats["bills_skipped"] += 1
            continue

        bill_db_id = row[0]  # surrogate id from bills.id (BIGSERIAL UNIQUE)
        stats["bills_inserted"] += 1

        # Insert each line item for this newly created bill
        for _, item_row in group.iterrows():
            code = item_row["item_code"]
            menu_item_id = menu_id_map.get(code)
            if menu_item_id is None:
                raise KeyError(
                    f"item_code {code!r} not in menu_id_map. "
                    "This should not happen — check _upsert_menu_items."
                )

            cur.execute(INSERT_BILL_ITEM, {
                "bill_id":      bill_db_id,
                "menu_item_id": menu_item_id,
                "quantity":     int(item_row["quantity"]),
                "unit_price":   float(item_row["unit_price"]),
                "line_total":   float(item_row["line_total"]),
            })
            stats["items_inserted"] += 1

    return stats


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    root_arg = sys.argv[2] if len(sys.argv) > 2 else "pos_exports"
    run_etl(date_arg, root_arg)
