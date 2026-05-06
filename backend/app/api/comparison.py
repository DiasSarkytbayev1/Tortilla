"""GET /api/comparison — design-doc §9.5."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.analytics import sql
from app.api.deps import CommonFilters, common_filters

router = APIRouter(tags=["analytics"])


class ComparisonRow(BaseModel):
    id: int
    name: str
    city: str
    bills: int
    revenue: float
    avg_ticket: float | None
    top_item: str | None
    peak_hour: int | None


@router.get("/comparison", response_model=list[ComparisonRow])
def comparison(f: Annotated[CommonFilters, Depends(common_filters)]) -> list[ComparisonRow]:
    rows = sql.comparison(
        from_d=f.from_d,
        to_d=f.to_d,
        restaurant_ids=f.restaurant_ids,
    )
    return [
        ComparisonRow(
            id=int(r["id"]),
            name=r["name"],
            city=r["city"],
            bills=int(r["bills"]),
            revenue=float(r["revenue"]),
            avg_ticket=float(r["avg_ticket"]) if r["avg_ticket"] is not None else None,
            top_item=r["top_item"],
            peak_hour=int(r["peak_hour"]) if r["peak_hour"] is not None else None,
        )
        for r in rows
    ]
