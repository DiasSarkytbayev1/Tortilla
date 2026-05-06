"""Tests for /api/comparison."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import needs_db


@needs_db
def test_returns_one_row_per_restaurant(authed_client: TestClient, isolated_data) -> None:
    res = authed_client.get(
        f"/api/comparison?from={isolated_data['from']}&to={isolated_data['to']}"
        f"&restaurants={isolated_data['restaurant_id']}"
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["bills"] == 2
    assert row["revenue"] == 27.0
    assert row["top_item"] is not None


@needs_db
def test_zero_bills_restaurant_returns_nulls(authed_client: TestClient) -> None:
    # Restaurant 1 (Madrid) has data only in seeded date ranges. Querying the
    # year 1900 should return rows with bills=0, top_item=None, etc.
    res = authed_client.get("/api/comparison?from=1900-01-01&to=1900-01-02&restaurants=1")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["bills"] == 0
    assert row["top_item"] is None
    assert row["peak_hour"] is None
    assert row["avg_ticket"] is None


@needs_db
def test_perf_under_budget(authed_client: TestClient) -> None:
    """Sanity check: full chain comparison query under 1.2s (design-doc §10.3)."""
    import time

    t0 = time.perf_counter()
    res = authed_client.get("/api/comparison?from=2026-01-01&to=2026-12-31")
    elapsed = time.perf_counter() - t0
    assert res.status_code == 200
    # 1.2s budget per design-doc §10.3
    assert elapsed < 1.2, f"comparison query took {elapsed:.2f}s, budget 1.2s"
