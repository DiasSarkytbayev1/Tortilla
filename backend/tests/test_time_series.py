"""Tests for /api/time-series."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import needs_db


@needs_db
def test_day_granularity(authed_client: TestClient, isolated_data) -> None:
    res = authed_client.get(
        f"/api/time-series?from={isolated_data['from']}&to={isolated_data['to']}"
        f"&restaurants={isolated_data['restaurant_id']}&granularity=day"
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["bills"] == 2


@needs_db
def test_hour_granularity_slices_by_hour(authed_client: TestClient, isolated_data) -> None:
    res = authed_client.get(
        f"/api/time-series?from={isolated_data['from']}&to={isolated_data['to']}"
        f"&restaurants={isolated_data['restaurant_id']}&granularity=hour"
    )
    assert res.status_code == 200
    rows = res.json()
    # 2 bills in 2 different hours → 2 buckets
    assert len(rows) == 2


@needs_db
def test_invalid_granularity_422(authed_client: TestClient) -> None:
    res = authed_client.get("/api/time-series?from=2026-01-01&to=2026-01-02&granularity=second")
    assert res.status_code == 422
