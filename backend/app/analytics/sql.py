"""
Pure SQL query functions for the analyst dashboard.

Every function takes its inputs, runs one parameterised query, and returns a
`list[dict]` ready to JSON-serialise. No printing, no formatting, no DataFrame.

This is the layer the FastAPI route handlers call. The CLI in
`app.analytics.queries` wraps the same SQL with print/DataFrame helpers — so
both surfaces stay in sync without duplicating SQL.

SQL bodies match docs/design-doc.md §9 verbatim where possible. Any deviation
is commented inline.
"""

from __future__ import annotations

from datetime import date

import psycopg2.extras

from app.config import CHAIN_TZ
from app.db import get_connection


def _query(sql: str, params: dict) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _to_naive_bounds(from_d: date, to_d: date) -> dict:
    """
    Convert (from, to) inclusive dates into the [from_ts, to_ts) window the
    SQL expects. `to_ts` is exclusive (= to + 1 day) so all bills sold on the
    `to` day are included.
    """
    return {"from_ts": from_d.isoformat(), "to_ts": to_d.isoformat()}


# ---------------------------------------------------------------------------
# Meta lookups
# ---------------------------------------------------------------------------


def list_restaurants() -> list[dict]:
    return _query(
        """
        SELECT id, name, city
        FROM restaurants
        ORDER BY name ASC
        """,
        {},
    )


def list_categories() -> list[dict]:
    rows = _query(
        """
        SELECT DISTINCT category
        FROM menu_items
        ORDER BY category ASC
        """,
        {},
    )
    return [{"category": r["category"]} for r in rows]


# ---------------------------------------------------------------------------
# Overview KPIs (design-doc §9.1)
# ---------------------------------------------------------------------------


def overview_kpis(
    from_d: date,
    to_d: date,
    restaurant_ids: list[int] | None,
) -> dict:
    """
    Returns the 5 KPIs for the Overview page in a single dict:
      revenue, bills, avg_ticket, top_item, peak_hour

    `top_item` is None and `peak_hour` is None when the range has no bills.
    """
    bounds = _to_naive_bounds(from_d, to_d)
    params = {
        **bounds,
        "restaurant_ids": restaurant_ids,
    }

    # Bill-level KPIs
    rows = _query(
        """
        SELECT
            COUNT(*)        AS bills,
            COALESCE(SUM(b.total), 0)    AS revenue,
            AVG(b.total)                 AS avg_ticket
        FROM bills b
        WHERE b.sold_at >= %(from_ts)s::timestamptz
          AND b.sold_at <  %(to_ts)s::timestamptz + interval '1 day'
          AND (%(restaurant_ids)s::int[] IS NULL
               OR b.restaurant_id = ANY(%(restaurant_ids)s::int[]))
        """,
        params,
    )
    bill_kpis = rows[0]

    # Top item by quantity sold (deterministic tie-break: lower menu_items.id)
    top_item_rows = _query(
        """
        SELECT m.id, m.name, m.category, SUM(bi.quantity)::bigint AS qty
        FROM bill_items bi
        JOIN bills      b  ON b.id = bi.bill_id
        JOIN menu_items m  ON m.id = bi.menu_item_id
        WHERE b.sold_at >= %(from_ts)s::timestamptz
          AND b.sold_at <  %(to_ts)s::timestamptz + interval '1 day'
          AND (%(restaurant_ids)s::int[] IS NULL
               OR b.restaurant_id = ANY(%(restaurant_ids)s::int[]))
        GROUP BY m.id, m.name, m.category
        ORDER BY qty DESC, m.id ASC
        LIMIT 1
        """,
        params,
    )
    top_item = top_item_rows[0] if top_item_rows else None

    # Peak hour (in chain TZ; tie-break: earlier hour)
    peak_rows = _query(
        """
        SELECT EXTRACT(HOUR FROM b.sold_at AT TIME ZONE %(tz)s)::int AS hour,
               COUNT(*) AS bills
        FROM bills b
        WHERE b.sold_at >= %(from_ts)s::timestamptz
          AND b.sold_at <  %(to_ts)s::timestamptz + interval '1 day'
          AND (%(restaurant_ids)s::int[] IS NULL
               OR b.restaurant_id = ANY(%(restaurant_ids)s::int[]))
        GROUP BY 1
        ORDER BY bills DESC, hour ASC
        LIMIT 1
        """,
        {**params, "tz": CHAIN_TZ},
    )
    peak_hour = peak_rows[0] if peak_rows else None

    return {
        "bills": int(bill_kpis["bills"] or 0),
        "revenue": float(bill_kpis["revenue"] or 0),
        "avg_ticket": float(bill_kpis["avg_ticket"]) if bill_kpis["avg_ticket"] is not None else None,
        "top_item": (
            {
                "id": top_item["id"],
                "name": top_item["name"],
                "category": top_item["category"],
                "qty": int(top_item["qty"]),
            }
            if top_item
            else None
        ),
        "peak_hour": ({"hour": int(peak_hour["hour"]), "bills": int(peak_hour["bills"])} if peak_hour else None),
    }


def overview_trend(
    from_d: date,
    to_d: date,
    restaurant_ids: list[int] | None,
) -> list[dict]:
    """Daily revenue + bills series for the Overview chart, in chain TZ."""
    return _query(
        """
        SELECT (b.sold_at AT TIME ZONE %(tz)s)::date AS day,
               COUNT(*)                AS bills,
               COALESCE(SUM(b.total), 0) AS revenue
        FROM bills b
        WHERE b.sold_at >= %(from_ts)s::timestamptz
          AND b.sold_at <  %(to_ts)s::timestamptz + interval '1 day'
          AND (%(restaurant_ids)s::int[] IS NULL
               OR b.restaurant_id = ANY(%(restaurant_ids)s::int[]))
        GROUP BY 1
        ORDER BY 1
        """,
        {
            **_to_naive_bounds(from_d, to_d),
            "restaurant_ids": restaurant_ids,
            "tz": CHAIN_TZ,
        },
    )


# ---------------------------------------------------------------------------
# Best Sellers (design-doc §9.2)
# ---------------------------------------------------------------------------

SQL_BEST_SELLERS = """
    SELECT
        m.id,
        m.code,
        m.name,
        m.category,
        SUM(bi.quantity)::bigint AS qty,
        SUM(bi.line_total)       AS revenue,
        ROUND(
            100.0 * SUM(bi.line_total) /
            NULLIF(SUM(SUM(bi.line_total)) OVER (), 0),
            2
        ) AS pct_of_total,
        COUNT(DISTINCT b.id)::bigint AS bills
    FROM bill_items bi
    JOIN bills      b ON b.id = bi.bill_id
    JOIN menu_items m ON m.id = bi.menu_item_id
    WHERE b.sold_at >= %(from_ts)s::timestamptz
      AND b.sold_at <  %(to_ts)s::timestamptz + interval '1 day'
      AND (%(restaurant_ids)s::int[] IS NULL
           OR b.restaurant_id = ANY(%(restaurant_ids)s::int[]))
      AND (%(categories)s::text[] IS NULL
           OR m.category = ANY(%(categories)s::text[]))
    GROUP BY m.id, m.code, m.name, m.category
    ORDER BY
        CASE WHEN %(rank_by)s = 'quantity' THEN SUM(bi.quantity)::numeric
             WHEN %(rank_by)s = 'revenue'  THEN SUM(bi.line_total)::numeric
        END DESC,
        m.id ASC
    LIMIT %(top_n)s
"""


def best_sellers(
    from_d: date,
    to_d: date,
    restaurant_ids: list[int] | None,
    categories: list[str] | None,
    rank_by: str,
    top_n: int,
) -> list[dict]:
    if rank_by not in ("quantity", "revenue"):
        raise ValueError("rank_by must be 'quantity' or 'revenue'")
    return _query(
        SQL_BEST_SELLERS,
        {
            **_to_naive_bounds(from_d, to_d),
            "restaurant_ids": restaurant_ids,
            "categories": categories,
            "rank_by": rank_by,
            "top_n": top_n,
        },
    )


# ---------------------------------------------------------------------------
# Time Series (design-doc §9.3)
# ---------------------------------------------------------------------------


# bucket_expr is interpolated, NOT user-supplied — picked from a fixed set so
# there's no SQL injection surface. See `time_series` below.
def _time_series_sql(bucket_expr: str) -> str:
    return f"""
        SELECT
            {bucket_expr} AS bucket,
            COUNT(*)                  AS bills,
            COALESCE(SUM(b.total), 0) AS revenue,
            AVG(b.total)              AS avg_ticket
        FROM bills b
        WHERE b.sold_at >= %(from_ts)s::timestamptz
          AND b.sold_at <  %(to_ts)s::timestamptz + interval '1 day'
          AND (%(restaurant_ids)s::int[] IS NULL
               OR b.restaurant_id = ANY(%(restaurant_ids)s::int[]))
        GROUP BY bucket
        ORDER BY bucket
    """


GRANULARITY_BUCKETS = {
    "hour": "date_trunc('hour', b.sold_at AT TIME ZONE %(tz)s)",
    "day": "(b.sold_at AT TIME ZONE %(tz)s)::date",
    "week": "date_trunc('week', b.sold_at AT TIME ZONE %(tz)s)::date",
    "month": "date_trunc('month', b.sold_at AT TIME ZONE %(tz)s)::date",
}


def time_series(
    from_d: date,
    to_d: date,
    restaurant_ids: list[int] | None,
    granularity: str,
) -> list[dict]:
    if granularity not in GRANULARITY_BUCKETS:
        raise ValueError(f"granularity must be one of {list(GRANULARITY_BUCKETS)}")
    sql = _time_series_sql(GRANULARITY_BUCKETS[granularity])
    return _query(
        sql,
        {
            **_to_naive_bounds(from_d, to_d),
            "restaurant_ids": restaurant_ids,
            "tz": CHAIN_TZ,
        },
    )


# ---------------------------------------------------------------------------
# Peak Hours (design-doc §9.4)
# ---------------------------------------------------------------------------


def peak_hours(
    from_d: date,
    to_d: date,
    restaurant_ids: list[int] | None,
) -> list[dict]:
    return _query(
        """
        SELECT
            EXTRACT(DOW  FROM b.sold_at AT TIME ZONE %(tz)s)::int AS dow,
            EXTRACT(HOUR FROM b.sold_at AT TIME ZONE %(tz)s)::int AS hour,
            COUNT(*)                  AS bills,
            COALESCE(SUM(b.total), 0) AS revenue
        FROM bills b
        WHERE b.sold_at >= %(from_ts)s::timestamptz
          AND b.sold_at <  %(to_ts)s::timestamptz + interval '1 day'
          AND (%(restaurant_ids)s::int[] IS NULL
               OR b.restaurant_id = ANY(%(restaurant_ids)s::int[]))
        GROUP BY dow, hour
        ORDER BY dow, hour
        """,
        {
            **_to_naive_bounds(from_d, to_d),
            "restaurant_ids": restaurant_ids,
            "tz": CHAIN_TZ,
        },
    )


# ---------------------------------------------------------------------------
# Restaurant Comparison (design-doc §9.5 — CTE rewrite)
# ---------------------------------------------------------------------------

SQL_COMPARISON = """
WITH bill_agg AS (
    SELECT
        b.restaurant_id,
        COUNT(*)     AS bills,
        SUM(b.total) AS revenue,
        AVG(b.total) AS avg_ticket
    FROM bills b
    WHERE b.sold_at >= %(from_ts)s::timestamptz
      AND b.sold_at <  %(to_ts)s::timestamptz + interval '1 day'
      AND (%(restaurant_ids)s::int[] IS NULL
           OR b.restaurant_id = ANY(%(restaurant_ids)s::int[]))
    GROUP BY b.restaurant_id
),
peak_hour_agg AS (
    SELECT DISTINCT ON (b.restaurant_id)
        b.restaurant_id,
        EXTRACT(HOUR FROM b.sold_at AT TIME ZONE %(tz)s)::int AS peak_hour
    FROM bills b
    WHERE b.sold_at >= %(from_ts)s::timestamptz
      AND b.sold_at <  %(to_ts)s::timestamptz + interval '1 day'
      AND (%(restaurant_ids)s::int[] IS NULL
           OR b.restaurant_id = ANY(%(restaurant_ids)s::int[]))
    GROUP BY b.restaurant_id, EXTRACT(HOUR FROM b.sold_at AT TIME ZONE %(tz)s)
    ORDER BY b.restaurant_id,
             COUNT(*) DESC,
             EXTRACT(HOUR FROM b.sold_at AT TIME ZONE %(tz)s) ASC
),
top_item_agg AS (
    SELECT DISTINCT ON (b.restaurant_id)
        b.restaurant_id,
        m.id   AS top_item_id,
        m.name AS top_item
    FROM bill_items bi
    JOIN bills      b ON b.id = bi.bill_id
    JOIN menu_items m ON m.id = bi.menu_item_id
    WHERE b.sold_at >= %(from_ts)s::timestamptz
      AND b.sold_at <  %(to_ts)s::timestamptz + interval '1 day'
      AND (%(restaurant_ids)s::int[] IS NULL
           OR b.restaurant_id = ANY(%(restaurant_ids)s::int[]))
    GROUP BY b.restaurant_id, m.id, m.name
    ORDER BY b.restaurant_id, SUM(bi.quantity) DESC, m.id ASC
)
SELECT
    r.id,
    r.name,
    r.city,
    COALESCE(ba.bills, 0)   AS bills,
    COALESCE(ba.revenue, 0) AS revenue,
    ba.avg_ticket           AS avg_ticket,
    ti.top_item             AS top_item,
    ph.peak_hour            AS peak_hour
FROM restaurants r
LEFT JOIN bill_agg      ba ON ba.restaurant_id = r.id
LEFT JOIN peak_hour_agg ph ON ph.restaurant_id = r.id
LEFT JOIN top_item_agg  ti ON ti.restaurant_id = r.id
WHERE (%(restaurant_ids)s::int[] IS NULL
       OR r.id = ANY(%(restaurant_ids)s::int[]))
ORDER BY revenue DESC NULLS LAST, r.id ASC
"""


def comparison(
    from_d: date,
    to_d: date,
    restaurant_ids: list[int] | None,
) -> list[dict]:
    return _query(
        SQL_COMPARISON,
        {
            **_to_naive_bounds(from_d, to_d),
            "restaurant_ids": restaurant_ids,
            "tz": CHAIN_TZ,
        },
    )
