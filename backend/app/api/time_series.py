"""GET /api/time-series — design-doc §9.3."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.analytics import sql
from app.api.deps import CommonFilters, common_filters

router = APIRouter(tags=["analytics"])


class TimeSeriesPoint(BaseModel):
    bucket: date | datetime
    bills: int
    revenue: float
    avg_ticket: float | None


@router.get("/time-series", response_model=list[TimeSeriesPoint])
def time_series(
    f: Annotated[CommonFilters, Depends(common_filters)],
    granularity: Annotated[Literal["hour", "day", "week", "month"], Query()] = "day",
) -> list[TimeSeriesPoint]:
    rows = sql.time_series(
        from_d=f.from_d,
        to_d=f.to_d,
        restaurant_ids=f.restaurant_ids,
        granularity=granularity,
    )
    return [
        TimeSeriesPoint(
            bucket=r["bucket"],
            bills=int(r["bills"]),
            revenue=float(r["revenue"]),
            avg_ticket=float(r["avg_ticket"]) if r["avg_ticket"] is not None else None,
        )
        for r in rows
    ]
