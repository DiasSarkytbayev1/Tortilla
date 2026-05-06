"""GET /api/peak-hours — design-doc §9.4."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.analytics import sql
from app.api.deps import CommonFilters, common_filters

router = APIRouter(tags=["analytics"])


class PeakHourCell(BaseModel):
    dow: int  # 0=Sun..6=Sat (Postgres EXTRACT(DOW))
    hour: int  # 0..23
    bills: int
    revenue: float


@router.get("/peak-hours", response_model=list[PeakHourCell])
def peak_hours(f: Annotated[CommonFilters, Depends(common_filters)]) -> list[PeakHourCell]:
    rows = sql.peak_hours(
        from_d=f.from_d,
        to_d=f.to_d,
        restaurant_ids=f.restaurant_ids,
    )
    return [
        PeakHourCell(
            dow=int(r["dow"]),
            hour=int(r["hour"]),
            bills=int(r["bills"]),
            revenue=float(r["revenue"]),
        )
        for r in rows
    ]
