"""Tests for /api/peak-hours."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import needs_db


@needs_db
def test_dow_hour_matrix(authed_client: TestClient, isolated_data) -> None:
    res = authed_client.get(
        f"/api/peak-hours?from={isolated_data['from']}&to={isolated_data['to']}"
        f"&restaurants={isolated_data['restaurant_id']}"
    )
    assert res.status_code == 200
    rows = res.json()
    # 2 bills in 2 different hours of the same DOW
    assert len(rows) == 2
    assert all(r["bills"] == 1 for r in rows)
    # All rows on the same DOW (April 15, 2026 — Wednesday → DOW=3)
    dows = {r["dow"] for r in rows}
    assert dows == {3}
