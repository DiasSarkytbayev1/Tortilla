"""GET /api/overview/kpis and /api/overview/trend — design-doc §9.1."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.analytics import sql
from app.api.deps import CommonFilters, common_filters

router = APIRouter(prefix="/overview", tags=["analytics"])


class TopItem(BaseModel):
    id: int
    name: str
    category: str
    qty: int


class PeakHour(BaseModel):
    hour: int
    bills: int


class KpisOut(BaseModel):
    bills: int
    revenue: float
    avg_ticket: float | None
    top_item: TopItem | None
    peak_hour: PeakHour | None


class KpisWithDelta(BaseModel):
    current: KpisOut
    previous: KpisOut


class TrendPoint(BaseModel):
    day: date
    bills: int
    revenue: float


@router.get("/kpis", response_model=KpisWithDelta)
def kpis(f: Annotated[CommonFilters, Depends(common_filters)]) -> KpisWithDelta:
    """
    Returns the 5 KPIs for the selected period, plus the same KPIs computed
    over the immediately preceding period of equal length, so the frontend
    can render the "vs previous N days" deltas (design-doc §9.1).
    """
    span_days = (f.to_d - f.from_d).days + 1  # inclusive
    from datetime import timedelta

    prev_to = f.from_d - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span_days - 1)

    current = sql.overview_kpis(f.from_d, f.to_d, f.restaurant_ids)
    previous = sql.overview_kpis(prev_from, prev_to, f.restaurant_ids)
    return KpisWithDelta(current=KpisOut(**current), previous=KpisOut(**previous))


@router.get("/trend", response_model=list[TrendPoint])
def trend(f: Annotated[CommonFilters, Depends(common_filters)]) -> list[TrendPoint]:
    rows = sql.overview_trend(f.from_d, f.to_d, f.restaurant_ids)
    return [TrendPoint(day=r["day"], bills=int(r["bills"]), revenue=float(r["revenue"])) for r in rows]
