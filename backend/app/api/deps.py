"""
Shared FastAPI dependencies for the /api router.

  require_user   — pulls user_id from the signed session cookie, raises 401 if
                   missing or stale. Mounted at the APIRouter level so every
                   route inside /api gets it for free.

  CommonFilters  — parses the (from, to, restaurants, categories) query params
                   that almost every analytics endpoint takes. Centralises
                   validation per design-doc §10.7.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, status

from app.auth.users import get_user_by_id
from app.validation import parse_categories, parse_date_range, parse_restaurant_ids

# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def require_user(request: Request) -> dict:
    """Returns {id, username, role} or raises 401."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = get_user_by_id(user_id)
    if not user:
        # Session points at a deleted user — clear the session and 401.
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session refers to a user that no longer exists",
        )
    return user


# ---------------------------------------------------------------------------
# Common analytics filters
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommonFilters:
    from_d: date
    to_d: date
    restaurant_ids: list[int] | None
    categories: list[str] | None


def common_filters(
    date_range: Annotated[tuple[date, date], Depends(parse_date_range)],
    restaurants: Annotated[str | None, Query()] = None,
    categories: Annotated[str | None, Query()] = None,
) -> CommonFilters:
    from_d, to_d = date_range
    return CommonFilters(
        from_d=from_d,
        to_d=to_d,
        restaurant_ids=parse_restaurant_ids(restaurants),
        categories=parse_categories(categories),
    )
