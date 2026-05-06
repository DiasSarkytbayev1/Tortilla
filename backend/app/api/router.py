"""
Composes the /api router.

  /api/auth/* is public (login uses no auth, /me + /logout use the require_user
  dependency individually).

  Everything else under /api/* is gated by `require_user` at the router level,
  so a new endpoint can't accidentally ship un-authenticated.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import auth, best_sellers, comparison, meta, overview, peak_hours, time_series
from app.api.deps import require_user

# Public router: only auth lives here. The auth router itself uses
# `require_user` on /me and /logout via per-route Depends().
public_api = APIRouter(prefix="/api")
public_api.include_router(auth.router)

# Protected router: everything else. The dependency runs before any of the
# included routers' handlers.
protected_api = APIRouter(prefix="/api", dependencies=[Depends(require_user)])
protected_api.include_router(meta.router)
protected_api.include_router(best_sellers.router)
protected_api.include_router(overview.router)
protected_api.include_router(time_series.router)
protected_api.include_router(peak_hours.router)
protected_api.include_router(comparison.router)
