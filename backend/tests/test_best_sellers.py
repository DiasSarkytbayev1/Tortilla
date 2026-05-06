"""Tests for /api/best-sellers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import needs_db


@needs_db
class TestBestSellers:
    def test_happy_path(self, authed_client: TestClient, isolated_data) -> None:
        res = authed_client.get(
            f"/api/best-sellers?from={isolated_data['from']}&to={isolated_data['to']}"
            f"&restaurants={isolated_data['restaurant_id']}"
        )
        assert res.status_code == 200
        rows = res.json()
        # 3 distinct items in the seeded data
        codes = [r["code"] for r in rows]
        assert {"TORTILLA_CLASSIC", "COFFEE", "TORTILLA_VEGAN"} <= set(codes)

    def test_rank_by_quantity(self, authed_client: TestClient, isolated_data) -> None:
        res = authed_client.get(
            f"/api/best-sellers?from={isolated_data['from']}&to={isolated_data['to']}"
            f"&restaurants={isolated_data['restaurant_id']}&rank_by=quantity"
        )
        assert res.status_code == 200
        rows = res.json()
        # All seeded items have qty=1 → tie-break by lower menu_items.id wins
        # → TORTILLA_CLASSIC (id=1) first.
        assert rows[0]["code"] == "TORTILLA_CLASSIC"

    def test_rank_by_revenue(self, authed_client: TestClient, isolated_data) -> None:
        res = authed_client.get(
            f"/api/best-sellers?from={isolated_data['from']}&to={isolated_data['to']}"
            f"&restaurants={isolated_data['restaurant_id']}&rank_by=revenue"
        )
        assert res.status_code == 200
        rows = res.json()
        # Highest single-line revenue is TORTILLA_VEGAN (9.00).
        assert rows[0]["code"] == "TORTILLA_VEGAN"
        assert rows[0]["revenue"] == 9.0

    def test_filter_by_category(self, authed_client: TestClient, isolated_data) -> None:
        res = authed_client.get(
            f"/api/best-sellers?from={isolated_data['from']}&to={isolated_data['to']}"
            f"&restaurants={isolated_data['restaurant_id']}&categories=drinks"
        )
        assert res.status_code == 200
        rows = res.json()
        assert all(r["category"] == "drinks" for r in rows)
        assert any(r["code"] == "COFFEE" for r in rows)

    def test_empty_range(self, authed_client: TestClient) -> None:
        # No bills sold in the year 1900.
        res = authed_client.get("/api/best-sellers?from=1900-01-01&to=1900-01-02")
        assert res.status_code == 200
        assert res.json() == []

    def test_invalid_range_400(self, authed_client: TestClient) -> None:
        res = authed_client.get("/api/best-sellers?from=2026-12-31&to=2026-01-01")
        assert res.status_code == 400

    def test_top_n_limit(self, authed_client: TestClient, isolated_data) -> None:
        res = authed_client.get(
            f"/api/best-sellers?from={isolated_data['from']}&to={isolated_data['to']}"
            f"&restaurants={isolated_data['restaurant_id']}&top_n=1"
        )
        assert res.status_code == 200
        assert len(res.json()) == 1
