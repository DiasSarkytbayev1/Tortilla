"""GET /api/best-sellers — design-doc §9.2."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.analytics import sql
from app.api.deps import CommonFilters, common_filters

router = APIRouter(tags=["analytics"])


class BestSellerRow(BaseModel):
    id: int
    code: str
    name: str
    category: str
    qty: int
    revenue: float
    pct_of_total: float | None
    bills: int


@router.get("/best-sellers", response_model=list[BestSellerRow])
def best_sellers(
    f: Annotated[CommonFilters, Depends(common_filters)],
    rank_by: Annotated[Literal["quantity", "revenue"], Query()] = "quantity",
    top_n: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[BestSellerRow]:
    rows = sql.best_sellers(
        from_d=f.from_d,
        to_d=f.to_d,
        restaurant_ids=f.restaurant_ids,
        categories=f.categories,
        rank_by=rank_by,
        top_n=top_n,
    )
    return [
        BestSellerRow(
            id=r["id"],
            code=r["code"],
            name=r["name"],
            category=r["category"],
            qty=int(r["qty"]),
            revenue=float(r["revenue"]),
            pct_of_total=float(r["pct_of_total"]) if r["pct_of_total"] is not None else None,
            bills=int(r["bills"]),
        )
        for r in rows
    ]
