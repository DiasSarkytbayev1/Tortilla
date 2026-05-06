"""
FastAPI entry point.

Routes:
  GET  /health                     liveness + DB reachability (public)
  POST /api/auth/login             cookie sign-in (public)
  GET  /api/auth/me                current user (auth required)
  POST /api/auth/logout            clear session (auth required)

  GET  /api/restaurants            (auth required)
  GET  /api/categories             (auth required)
  GET  /api/best-sellers           (auth required)
  GET  /api/overview/kpis          (auth required)
  GET  /api/overview/trend         (auth required)
  GET  /api/time-series            (auth required)
  GET  /api/peak-hours             (auth required)
  GET  /api/comparison             (auth required)
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import protected_api, public_api
from app.config import COOKIE_SECURE, SECRET_KEY, SESSION_TTL_S, assert_secret_key_set
from app.db import get_connection

assert_secret_key_set()

app = FastAPI(title="Tortilla Analytics API", version="0.1.0")

# Signed session cookie. HttpOnly + SameSite=Lax + Secure-in-prod (per plan §11).
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=SESSION_TTL_S,
    same_site="lax",
    https_only=COOKIE_SECURE,
)

app.include_router(public_api)
app.include_router(protected_api)


@app.get("/health")
def health() -> dict:
    """Liveness + DB reachability."""
    db_ok = False
    db_error: str | None = None
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            db_ok = True
        finally:
            conn.close()
    except Exception as exc:
        db_error = str(exc)

    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "unreachable",
        "db_error": db_error,
    }
