"""
Three analytical queries that answer the core PRD questions.

  1. best_sellers()           — "What's our best-selling dish?"
  2. peak_hours()              — "When do we get hammered on Saturdays?"
  3. restaurant_comparison()   — "How does Restaurant A compare to B?"

Each function prints a formatted table to stdout AND returns a pandas
DataFrame so results can be used programmatically (CLI today, FastAPI
routes once the dashboard endpoints are wired).
"""

from datetime import datetime

import pandas as pd
import psycopg2.extras

from app.config import CHAIN_TZ, CURRENCY_SYMBOL
from app.db import get_connection

# PostgreSQL EXTRACT(DOW) → 0=Sun, 1=Mon … 6=Sat
DOW_LABELS = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}


def _query(sql: str, params: dict | None = None) -> pd.DataFrame:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or {})
            rows = cur.fetchall()
            return pd.DataFrame([dict(r) for r in rows])
    finally:
        conn.close()


def _parse_date(date_str: str, label: str) -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{label} must be YYYY-MM-DD, got: {date_str!r}") from None
    return date_str


# ---------------------------------------------------------------------------
# 1. BEST SELLERS
# ---------------------------------------------------------------------------

SQL_BEST_SELLERS = """
    SELECT
        mi.code                             AS item_code,
        mi.name                             AS item_name,
        mi.category                         AS category,
        SUM(bi.quantity)                    AS units_sold,
        SUM(bi.line_total)                  AS revenue,
        ROUND(AVG(bi.unit_price), 2)        AS avg_unit_price,
        COUNT(DISTINCT b.id)                AS appeared_in_bills
    FROM bill_items  bi
    JOIN bills       b  ON bi.bill_id      = b.id
    JOIN menu_items  mi ON bi.menu_item_id = mi.id
    WHERE b.sold_at >= %(from_date)s::timestamptz
      AND b.sold_at <  %(to_date)s::timestamptz + interval '1 day'
      AND (%(restaurant_id)s IS NULL OR b.restaurant_id = %(restaurant_id)s::int)
      AND (%(category)s      IS NULL OR mi.category     = %(category)s)
    GROUP BY mi.id, mi.code, mi.name, mi.category
    ORDER BY units_sold DESC, revenue DESC
    LIMIT %(top_n)s
"""


def best_sellers(
    from_date: str,
    to_date: str,
    restaurant_id: int | None = None,
    category: str | None = None,
    top_n: int = 10,
) -> pd.DataFrame:
    _parse_date(from_date, "from_date")
    _parse_date(to_date, "to_date")

    df = _query(
        SQL_BEST_SELLERS,
        {
            "from_date": from_date,
            "to_date": to_date,
            "restaurant_id": restaurant_id,
            "category": category,
            "top_n": top_n,
        },
    )

    if df.empty:
        print("No data found for the given filters.")
        return df

    df["revenue"] = df["revenue"].astype(float)
    df["rank"] = range(1, len(df) + 1)

    _print_header("BEST SELLERS", from_date, to_date, restaurant_id, category)
    _print_table(
        df[["rank", "item_name", "category", "units_sold", "revenue", "appeared_in_bills"]],
        col_renames={
            "item_name": "Item",
            "category": "Category",
            "units_sold": "Units sold",
            "revenue": f"Revenue ({CURRENCY_SYMBOL})",
            "appeared_in_bills": "Bills",
        },
        money_cols=[f"Revenue ({CURRENCY_SYMBOL})"],
    )
    return df


# ---------------------------------------------------------------------------
# 2. PEAK HOURS
# ---------------------------------------------------------------------------

SQL_PEAK_HOURS = """
    SELECT
        EXTRACT(DOW  FROM b.sold_at AT TIME ZONE %(tz)s)::int   AS day_of_week,
        EXTRACT(HOUR FROM b.sold_at AT TIME ZONE %(tz)s)::int   AS hour_of_day,
        COUNT(*)           AS bill_count,
        SUM(b.total)       AS revenue,
        ROUND(AVG(b.total), 2) AS avg_ticket
    FROM bills b
    WHERE b.sold_at >= %(from_date)s::timestamptz
      AND b.sold_at <  %(to_date)s::timestamptz + interval '1 day'
      AND (%(restaurant_id)s IS NULL OR b.restaurant_id = %(restaurant_id)s::int)
    GROUP BY 1, 2
    ORDER BY 1, 2
"""


def peak_hours(
    from_date: str,
    to_date: str,
    restaurant_id: int | None = None,
) -> pd.DataFrame:
    _parse_date(from_date, "from_date")
    _parse_date(to_date, "to_date")

    df = _query(
        SQL_PEAK_HOURS,
        {
            "from_date": from_date,
            "to_date": to_date,
            "restaurant_id": restaurant_id,
            "tz": CHAIN_TZ,
        },
    )

    if df.empty:
        print("No data found for the given filters.")
        return df

    df["revenue"] = df["revenue"].astype(float)
    df["avg_ticket"] = df["avg_ticket"].astype(float)
    df["day_label"] = df["day_of_week"].map(DOW_LABELS)

    _print_header("PEAK HOURS", from_date, to_date, restaurant_id)
    print(f"  Timezone: {CHAIN_TZ}\n")

    pivot = df.pivot_table(
        index="day_label",
        columns="hour_of_day",
        values="bill_count",
        aggfunc="sum",
        fill_value=0,
    ).reindex([DOW_LABELS[i] for i in [1, 2, 3, 4, 5, 6, 0]])

    print("  Bill count by day × hour:")
    print(pivot.to_string())
    print()

    if not df.empty:
        peak_row = df.loc[df["bill_count"].idxmax()]
        print(
            f"  Busiest slot: {peak_row['day_label']}  "
            f"{int(peak_row['hour_of_day']):02d}:00  "
            f"({int(peak_row['bill_count'])} bills, "
            f"{CURRENCY_SYMBOL}{peak_row['revenue']:,.2f} revenue)"
        )
    print()

    return df


# ---------------------------------------------------------------------------
# 3. RESTAURANT COMPARISON
# ---------------------------------------------------------------------------

SQL_COMPARISON = """
    SELECT
        r.id                                    AS restaurant_id,
        r.name                                  AS restaurant_name,
        r.city                                  AS city,
        COUNT(DISTINCT b.id)                    AS bill_count,
        COALESCE(SUM(b.total),        0)        AS total_revenue,
        COALESCE(ROUND(AVG(b.total), 2), 0)     AS avg_ticket,
        COALESCE(SUM(bi.quantity),    0)        AS items_sold,
        COALESCE(
            ROUND(SUM(b.total) / NULLIF(COUNT(DISTINCT b.id), 0), 2),
            0
        )                                       AS revenue_per_bill
    FROM restaurants r
    LEFT JOIN bills b
           ON r.id = b.restaurant_id
          AND b.sold_at >= %(from_date)s::timestamptz
          AND b.sold_at <  %(to_date)s::timestamptz + interval '1 day'
    LEFT JOIN bill_items bi ON b.id = bi.bill_id
    GROUP BY r.id, r.name, r.city
    ORDER BY total_revenue DESC NULLS LAST
"""


def restaurant_comparison(from_date: str, to_date: str) -> pd.DataFrame:
    _parse_date(from_date, "from_date")
    _parse_date(to_date, "to_date")

    df = _query(SQL_COMPARISON, {"from_date": from_date, "to_date": to_date})

    if df.empty:
        print("No data found.")
        return df

    for col in ("total_revenue", "avg_ticket", "revenue_per_bill"):
        df[col] = df[col].astype(float)

    df["rank"] = range(1, len(df) + 1)

    totals = {
        "rank": "—",
        "restaurant_name": "CHAIN TOTAL",
        "city": "",
        "bill_count": df["bill_count"].sum(),
        "total_revenue": df["total_revenue"].sum(),
        "avg_ticket": df["avg_ticket"].mean(),
        "items_sold": df["items_sold"].sum(),
    }

    display_df = pd.concat(
        [
            df[["rank", "restaurant_name", "city", "bill_count", "total_revenue", "avg_ticket", "items_sold"]],
            pd.DataFrame([totals]),
        ],
        ignore_index=True,
    )

    _print_header("RESTAURANT COMPARISON", from_date, to_date)
    _print_table(
        display_df,
        col_renames={
            "restaurant_name": "Restaurant",
            "city": "City",
            "bill_count": "Bills",
            "total_revenue": f"Revenue ({CURRENCY_SYMBOL})",
            "avg_ticket": f"Avg ticket ({CURRENCY_SYMBOL})",
            "items_sold": "Items sold",
        },
        money_cols=[f"Revenue ({CURRENCY_SYMBOL})", f"Avg ticket ({CURRENCY_SYMBOL})"],
    )
    return df


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _print_header(
    title: str,
    from_date: str = "",
    to_date: str = "",
    restaurant_id=None,
    category: str | None = None,
) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    if from_date and to_date:
        print(f"  Period : {from_date} → {to_date}")
    if restaurant_id is not None:
        print(f"  Filter : restaurant_id = {restaurant_id}")
    if category:
        print(f"  Filter : category = {category!r}")
    print(f"{'─' * 60}")


def _print_table(df: pd.DataFrame, col_renames: dict, money_cols: list) -> None:
    display = df.rename(columns=col_renames).copy()
    for col in money_cols:
        if col in display.columns:
            display[col] = display[col].apply(lambda v: f"{float(v):>10,.2f}" if isinstance(v, (int, float)) else v)
    print(display.to_string(index=False))
    print()
