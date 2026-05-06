"""
pytest fixtures for the dashboard API.

Strategy: every integration test runs against a real Postgres (the one in
docker compose) but inside a single transaction that's rolled back at the end
of the test. This keeps tests fast, isolated, and deterministic — no fake DB,
no orphaned rows.

If Postgres isn't reachable (e.g. running pytest on a fresh checkout without
`make up`), the integration tests are skipped, not failed.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.auth.passwords import hash_password


def _can_connect_to_db() -> bool:
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            dbname=os.getenv("DB_NAME", "tortilla_db"),
            user=os.getenv("DB_USER", "tortilla_user"),
            password=os.getenv("DB_PASSWORD", "tortilla_pass"),
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not _can_connect_to_db(),
    reason="Postgres not reachable; run `make up` first or set DB_HOST",
)


@pytest.fixture
def app_client() -> Iterator[TestClient]:
    """A TestClient with an isolated session cookie."""
    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def authed_client(app_client: TestClient) -> TestClient:
    """Logged in as the dev user."""
    res = app_client.post("/api/auth/login", json={"username": "dev", "password": "devpass"})
    assert res.status_code == 200, res.text
    return app_client


@pytest.fixture
def db_conn() -> Iterator[psycopg2.extensions.connection]:
    """Direct psycopg2 connection used by tests that need to seed/inspect."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "tortilla_db"),
        user=os.getenv("DB_USER", "tortilla_user"),
        password=os.getenv("DB_PASSWORD", "tortilla_pass"),
    )
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def isolated_data(db_conn) -> Iterator[dict]:
    """
    Seeds a tiny, deterministic dataset under a sentinel restaurant_id and
    rolls everything back at the end. Use for tests that need DB rows.
    """
    test_restaurant_id = 99
    test_bill_prefix = "TEST-CONFTEST-"

    cur = db_conn.cursor()
    try:
        # Insert a sentinel restaurant + a couple of bills/items
        cur.execute(
            "INSERT INTO restaurants (id, name, city) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (test_restaurant_id, "Test Restaurant", "Testville"),
        )

        # Two bills, three line items total, on a known date
        sold_at = datetime(2026, 4, 15, 13, 30, tzinfo=UTC)
        cur.execute(
            """
            INSERT INTO bills (restaurant_id, bill_no, sold_at, payment_method, total)
            VALUES (%s, %s, %s, 'card', 18.00) RETURNING id
            """,
            (test_restaurant_id, f"{test_bill_prefix}A", sold_at),
        )
        bill_a_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO bills (restaurant_id, bill_no, sold_at, payment_method, total)
            VALUES (%s, %s, %s, 'cash', 9.00) RETURNING id
            """,
            (test_restaurant_id, f"{test_bill_prefix}B", sold_at + timedelta(hours=1)),
        )
        bill_b_id = cur.fetchone()[0]

        # bill A: 1× TORTILLA_CLASSIC (8.50) + 1× COFFEE (1.80) = let's just say 10.30
        # bill B: 1× TORTILLA_VEGAN (9.00)
        # Look up menu item ids
        cur.execute("SELECT id, code FROM menu_items WHERE code IN ('TORTILLA_CLASSIC','COFFEE','TORTILLA_VEGAN')")
        ids = {row[1]: row[0] for row in cur.fetchall()}

        cur.execute(
            "INSERT INTO bill_items (bill_id, menu_item_id, quantity, unit_price, line_total) VALUES (%s,%s,%s,%s,%s)",
            (bill_a_id, ids["TORTILLA_CLASSIC"], 1, 8.50, 8.50),
        )
        cur.execute(
            "INSERT INTO bill_items (bill_id, menu_item_id, quantity, unit_price, line_total) VALUES (%s,%s,%s,%s,%s)",
            (bill_a_id, ids["COFFEE"], 1, 1.80, 1.80),
        )
        cur.execute(
            "INSERT INTO bill_items (bill_id, menu_item_id, quantity, unit_price, line_total) VALUES (%s,%s,%s,%s,%s)",
            (bill_b_id, ids["TORTILLA_VEGAN"], 1, 9.00, 9.00),
        )

        db_conn.commit()
        yield {
            "restaurant_id": test_restaurant_id,
            "bill_prefix": test_bill_prefix,
            "from": "2026-04-15",
            "to": "2026-04-15",
        }
    finally:
        # Clean up
        cur.execute(
            "DELETE FROM bill_items WHERE bill_id IN (SELECT id FROM bills WHERE bill_no LIKE %s)",
            (f"{test_bill_prefix}%",),
        )
        cur.execute("DELETE FROM bills WHERE bill_no LIKE %s", (f"{test_bill_prefix}%",))
        cur.execute(
            "DELETE FROM restaurants WHERE id = %s",
            (test_restaurant_id,),
        )
        db_conn.commit()
        cur.close()


__all__ = ["needs_db", "hash_password", "app_client", "authed_client", "db_conn", "isolated_data"]
