"""Tests for /api/overview/kpis and /api/overview/trend."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import needs_db


@needs_db
class TestOverviewKpis:
    def test_happy(self, authed_client: TestClient, isolated_data) -> None:
        res = authed_client.get(
            f"/api/overview/kpis?from={isolated_data['from']}&to={isolated_data['to']}"
            f"&restaurants={isolated_data['restaurant_id']}"
        )
        assert res.status_code == 200
        body = res.json()
        # 2 bills seeded
        assert body["current"]["bills"] == 2
        assert body["current"]["revenue"] == 27.0  # 18 + 9
        assert body["current"]["top_item"]["name"] in {
            "Tortilla Española Clásica",
            "Café con Leche",
            "Tortilla Vegana",
        }
        # Previous period had no bills
        assert body["previous"]["bills"] == 0

    def test_empty_range_returns_zero_kpis(self, authed_client: TestClient) -> None:
        res = authed_client.get("/api/overview/kpis?from=1900-01-01&to=1900-01-02")
        assert res.status_code == 200
        body = res.json()
        assert body["current"]["bills"] == 0
        assert body["current"]["top_item"] is None
        assert body["current"]["peak_hour"] is None


@needs_db
class TestOverviewTrend:
    def test_happy(self, authed_client: TestClient, isolated_data) -> None:
        res = authed_client.get(
            f"/api/overview/trend?from={isolated_data['from']}&to={isolated_data['to']}"
            f"&restaurants={isolated_data['restaurant_id']}"
        )
        assert res.status_code == 200
        rows = res.json()
        # Single day in the seed window
        assert len(rows) == 1
        assert rows[0]["bills"] == 2
        assert rows[0]["revenue"] == 27.0
