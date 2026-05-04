"""
generate_mock_csv.py
────────────────────
Generates one flat CSV file per restaurant per day, simulating the daily
export that a POS terminal produces.

Each row = one bill_item line, with the parent bill and menu_item fields
denormalised alongside it — exactly the shape a POS exports before it hits
the normalisation/ETL layer.

Column layout mirrors the target tables:
  bills        → restaurant_id, bill_no, sold_at, payment_method, bill_total
  bill_items   → quantity, unit_price, line_total
  menu_items   → item_code, item_name, item_category
  (restaurant) → restaurant_name, restaurant_city   [convenience columns]

Usage
-----
    python generate_mock_csv.py                  # generates for today
    python generate_mock_csv.py 2026-05-01       # generates for a specific date

Output
------
    pos_exports/
    └── 2026-05-01/
        ├── restaurant_1.csv
        ├── restaurant_2.csv
        …
        └── restaurant_10.csv
"""

import os
import sys
import uuid
import shutil
import random
from datetime import datetime, timedelta, timezone

import pandas as pd
from faker import Faker

fake = Faker("es_ES")

# ---------------------------------------------------------------------------
# FIXED RESTAURANT REGISTRY
# IDs must match init_db.sql exactly — never change the order.
# ---------------------------------------------------------------------------
RESTAURANTS = {
    1:  {"name": "La Tortilla de Oro",    "city": "Madrid"},
    2:  {"name": "El Rincón Tortillero",  "city": "Barcelona"},
    3:  {"name": "Tortillería Valencia",  "city": "Valencia"},
    4:  {"name": "Casa Tortilla Sevilla", "city": "Sevilla"},
    5:  {"name": "La Tortilla Maña",      "city": "Zaragoza"},
    6:  {"name": "Tortillería del Sur",   "city": "Málaga"},
    7:  {"name": "Tortilla La Huerta",    "city": "Murcia"},
    8:  {"name": "Tortilla Balear",       "city": "Palma"},
    9:  {"name": "Euskal Tortilla",       "city": "Bilbao"},
    10: {"name": "Tortillería Levante",   "city": "Alicante"},
}

# ---------------------------------------------------------------------------
# FIXED MENU CATALOG
# Codes must match init_db.sql exactly.
# ---------------------------------------------------------------------------
MENU_ITEMS = [
    {"code": "TORTILLA_CLASSIC",  "name": "Tortilla Española Clásica", "category": "tortilla", "price": 8.50},
    {"code": "TORTILLA_ONION",    "name": "Tortilla con Cebolla",      "category": "tortilla", "price": 8.50},
    {"code": "TORTILLA_NO_ONION", "name": "Tortilla sin Cebolla",      "category": "tortilla", "price": 8.50},
    {"code": "TORTILLA_VEGAN",    "name": "Tortilla Vegana",           "category": "tortilla", "price": 9.00},
    {"code": "TORTILLA_JAMON",    "name": "Tortilla con Jamón",        "category": "tortilla", "price": 10.50},
    {"code": "BREAD",             "name": "Pan Tostado",               "category": "sides",    "price": 2.00},
    {"code": "ALIOLI",            "name": "Alioli Casero",             "category": "sides",    "price": 1.50},
    {"code": "SALAD_GREEN",       "name": "Ensalada Verde",            "category": "sides",    "price": 4.50},
    {"code": "COFFEE",            "name": "Café con Leche",            "category": "drinks",   "price": 1.80},
    {"code": "JUICE_OJ",          "name": "Zumo de Naranja Natural",   "category": "drinks",   "price": 2.50},
    {"code": "WATER",             "name": "Agua Mineral",              "category": "drinks",   "price": 1.20},
    {"code": "BEER",              "name": "Cerveza Caña",              "category": "drinks",   "price": 2.80},
    {"code": "WINE_GLASS",        "name": "Vino de la Casa",           "category": "drinks",   "price": 3.20},
    {"code": "SOFT_DRINK",        "name": "Refresco",                  "category": "drinks",   "price": 2.20},
]

# Weighted selection so tortillas appear more often than side dishes
MENU_WEIGHTS = [25, 25, 20, 10, 15,  8, 5, 6,  20, 10, 12, 15, 8, 10]

PAYMENT_METHODS = ["cash", "card", "contactless"]

BASE_DIR = "pos_exports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_timestamp(date_obj: datetime) -> datetime:
    """
    Random UTC timestamp within the given day, weighted toward lunch
    (12-15h) and dinner (20-23h) peaks to mimic real restaurant traffic.
    """
    # Pick a random hour using a traffic distribution
    hours = list(range(8, 24))
    weights = [
        1, 2, 3, 5,   # 08-11 (light breakfast traffic)
        8, 9, 8, 5,   # 12-15 (lunch peak)
        3, 3, 3, 4,   # 16-19 (afternoon + early dinner)
        7, 8, 6, 4,   # 20-23 (dinner peak)
    ]
    hour = random.choices(hours, weights=weights, k=1)[0]
    minute = random.randint(0, 59)
    second = random.randint(0, 59)

    # Combine with the date, then attach UTC timezone
    naive = date_obj.replace(hour=hour, minute=minute, second=second, microsecond=0)
    return naive.replace(tzinfo=timezone.utc)


def generate_bill(restaurant_id: int, date_obj: datetime) -> list[dict]:
    """
    Returns a list of flat rows (one per bill_item) representing a single bill.
    All bill-level fields are repeated on every row — this is the POS export format.
    """
    restaurant = RESTAURANTS[restaurant_id]
    bill_no = f"BILL-{uuid.uuid4().hex[:12].upper()}"
    sold_at = random_timestamp(date_obj)
    payment_method = random.choice(PAYMENT_METHODS)

    # Every bill has 1-5 line items; at least one tortilla item
    n_items = random.randint(1, 5)

    # Force the first item to be a tortilla for realistic receipts
    tortilla_items = [m for m in MENU_ITEMS if m["category"] == "tortilla"]
    first_item = random.choice(tortilla_items)
    chosen_items: list[dict] = [first_item]

    for _ in range(n_items - 1):
        chosen_items.append(
            random.choices(MENU_ITEMS, weights=MENU_WEIGHTS, k=1)[0]
        )

    rows = []
    bill_total = 0.0

    for item in chosen_items:
        quantity = random.randint(1, 3)
        unit_price = item["price"]
        line_total = round(quantity * unit_price, 2)
        bill_total += line_total

        rows.append({
            "restaurant_id":   restaurant_id,
            "restaurant_name": restaurant["name"],
            "restaurant_city": restaurant["city"],
            "bill_no":         bill_no,
            "sold_at":         sold_at.isoformat(),  # ISO-8601 UTC
            "payment_method":  payment_method,
            "bill_total":      round(bill_total, 2),  # filled in below
            "item_code":       item["code"],
            "item_name":       item["name"],
            "item_category":   item["category"],
            "quantity":        quantity,
            "unit_price":      unit_price,
            "line_total":      line_total,
        })

    # Backfill the true bill_total (sum of all lines) on every row
    bill_total = round(bill_total, 2)
    for row in rows:
        row["bill_total"] = bill_total

    return rows


def generate_restaurant_csv(restaurant_id: int, date_obj: datetime) -> pd.DataFrame:
    """
    Generates a day's worth of bills for one restaurant.
    Volume is randomised per restaurant to simulate size differences.
    """
    # Larger-city restaurants get more traffic
    city = RESTAURANTS[restaurant_id]["city"]
    big_cities = {"Madrid", "Barcelona", "Valencia", "Sevilla"}
    n_bills = random.randint(80, 200) if city in big_cities else random.randint(30, 80)

    all_rows = []
    for _ in range(n_bills):
        all_rows.extend(generate_bill(restaurant_id, date_obj))

    return pd.DataFrame(all_rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_exports(report_date: str | None = None) -> None:
    """
    Generates one CSV per restaurant for the given date.

    Parameters
    ----------
    report_date : str, optional
        Date in YYYY-MM-DD format.  Defaults to today (UTC).
    """
    if report_date:
        try:
            date_obj = datetime.strptime(report_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Date must be YYYY-MM-DD, got: {report_date!r}")
    else:
        date_obj = datetime.utcnow()

    date_str = date_obj.strftime("%Y-%m-%d")
    date_path = os.path.join(BASE_DIR, date_str)

    # Idempotent: overwrite existing output for this date
    if os.path.exists(date_path):
        print(f"[INFO] Overwriting existing exports for {date_str}")
        shutil.rmtree(date_path)

    os.makedirs(date_path, exist_ok=True)
    print(f"[INFO] Generating POS exports for {date_str} — {len(RESTAURANTS)} restaurants")

    total_rows = 0
    for restaurant_id in RESTAURANTS:
        df = generate_restaurant_csv(restaurant_id, date_obj)
        file_path = os.path.join(date_path, f"restaurant_{restaurant_id}.csv")
        df.to_csv(file_path, index=False)
        total_rows += len(df)
        print(f"  [+] restaurant_{restaurant_id}.csv  ({len(df):>5} rows)")

    print(f"[DONE] {total_rows:,} total rows written to {date_path}/")


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    generate_exports(date_arg)
