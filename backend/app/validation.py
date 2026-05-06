"""
Request validation helpers shared across API endpoints.

Single source of truth for the date-range guard rails:
  - from > to                 → 400
  - range > 2 years (730d)    → 400 (design-doc §10.7 — anything longer is a
                                     report-run problem, not a dashboard query)
  - malformed ISO date string → 400

Endpoints inject `parse_date_range` via `Depends(...)` so the same checks run
on every entry point. Keep this file dependency-free (no DB, no auth) so it
stays trivial to test.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import HTTPException, Query, status

MAX_RANGE_DAYS = 730  # 2 years, design-doc §10.7


def _parse_iso_date(s: str, label: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} must be YYYY-MM-DD, got: {s!r}",
        ) from e


def parse_date_range(
    from_: Annotated[str, Query(alias="from")],
    to: Annotated[str, Query()],
) -> tuple[date, date]:
    """
    FastAPI dependency. Use as:

        @router.get("/best-sellers")
        def best_sellers(dr: tuple[date, date] = Depends(parse_date_range), ...):
            from_d, to_d = dr
            ...

    The `from` query param is aliased because `from` is a Python keyword.
    """
    from_d = _parse_iso_date(from_, "from")
    to_d = _parse_iso_date(to, "to")

    if from_d > to_d:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"from ({from_d}) must be <= to ({to_d})",
        )

    span = (to_d - from_d).days
    if span > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"date range too wide ({span} days); "
                f"max is {MAX_RANGE_DAYS} days. "
                "Run a separate report job for longer ranges."
            ),
        )

    return from_d, to_d


def parse_restaurant_ids(value: str | None) -> list[int] | None:
    """
    Parse a comma-separated `restaurants=1,2,5` query param into a list of
    ints. Returns None when missing or empty (design-doc §8 URL encoding rule:
    omitted means "all").

    Raises 400 on `?restaurants=` (empty) or non-int values.
    """
    if value is None:
        return None
    if value == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="restaurants= cannot be empty (omit the param for 'all')",
        )
    try:
        ids = [int(x) for x in value.split(",")]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"restaurants must be a comma-separated list of ints, got: {value!r}",
        ) from e
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="restaurants must contain at least one id",
        )
    return ids


def parse_categories(value: str | None) -> list[str] | None:
    """
    Parse a comma-separated `categories=tortilla,drinks` query param.
    Returns None when missing or empty.
    """
    if value is None:
        return None
    if value == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="categories= cannot be empty (omit the param for 'all')",
        )
    cats = [c.strip() for c in value.split(",") if c.strip()]
    if not cats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="categories must contain at least one value",
        )
    return cats
