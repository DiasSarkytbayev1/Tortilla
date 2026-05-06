"""
FastAPI entry point.

V1 surface is intentionally minimal:
  GET /health  → liveness check + Postgres reachability

Real analytics endpoints (per design-doc §11) are added in a follow-up:
  GET /api/restaurants
  GET /api/best-sellers
  GET /api/time-series
  GET /api/peak-hours
  GET /api/comparison
"""

from fastapi import FastAPI

from app.db import get_connection

app = FastAPI(title="Tortilla Analytics API", version="0.1.0")


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
