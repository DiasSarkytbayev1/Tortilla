"""Tests for /api/restaurants and /api/categories."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import needs_db


@needs_db
def test_list_restaurants(authed_client: TestClient) -> None:
    res = authed_client.get("/api/restaurants")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) >= 10  # 10 seeded restaurants from init_db.sql
    assert all(set(r.keys()) == {"id", "name", "city"} for r in rows)
    assert any(r["name"] == "La Tortilla de Oro" for r in rows)


@needs_db
def test_list_categories(authed_client: TestClient) -> None:
    res = authed_client.get("/api/categories")
    assert res.status_code == 200
    rows = res.json()
    cats = [r["category"] for r in rows]
    assert "tortilla" in cats
    assert "drinks" in cats
    assert "sides" in cats
