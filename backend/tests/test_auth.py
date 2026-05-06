"""Auth endpoint tests — needs DB for the dev user lookup."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import needs_db


@needs_db
class TestAuth:
    def test_login_happy(self, app_client: TestClient) -> None:
        res = app_client.post("/api/auth/login", json={"username": "dev", "password": "devpass"})
        assert res.status_code == 200
        body = res.json()
        assert body["username"] == "dev"
        assert body["role"] == "analyst"

    def test_login_wrong_password(self, app_client: TestClient) -> None:
        res = app_client.post("/api/auth/login", json={"username": "dev", "password": "WRONG"})
        assert res.status_code == 401

    def test_login_unknown_user(self, app_client: TestClient) -> None:
        res = app_client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
        assert res.status_code == 401

    def test_me_no_session(self, app_client: TestClient) -> None:
        res = app_client.get("/api/auth/me")
        assert res.status_code == 401

    def test_me_with_session(self, authed_client: TestClient) -> None:
        res = authed_client.get("/api/auth/me")
        assert res.status_code == 200
        assert res.json()["username"] == "dev"

    def test_logout_clears_session(self, authed_client: TestClient) -> None:
        # Pre-condition: /me works
        assert authed_client.get("/api/auth/me").status_code == 200
        # Logout
        assert authed_client.post("/api/auth/logout").status_code == 204
        # /me now 401
        assert authed_client.get("/api/auth/me").status_code == 401

    def test_protected_routes_require_auth(self, app_client: TestClient) -> None:
        # Without session, every analytics endpoint must be 401.
        for path in [
            "/api/restaurants",
            "/api/categories",
            "/api/best-sellers?from=2026-01-01&to=2026-01-02",
            "/api/overview/kpis?from=2026-01-01&to=2026-01-02",
            "/api/peak-hours?from=2026-01-01&to=2026-01-02",
        ]:
            assert app_client.get(path).status_code == 401, path

    def test_login_validation_short_password(self, app_client: TestClient) -> None:
        res = app_client.post("/api/auth/login", json={"username": "dev", "password": ""})
        assert res.status_code == 422
