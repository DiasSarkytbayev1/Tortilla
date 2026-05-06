"""GET /api/restaurants and GET /api/categories."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.analytics import sql

router = APIRouter(tags=["meta"])


class RestaurantOut(BaseModel):
    id: int
    name: str
    city: str


class CategoryOut(BaseModel):
    category: str


@router.get("/restaurants", response_model=list[RestaurantOut])
def list_restaurants() -> list[RestaurantOut]:
    return [RestaurantOut(**r) for r in sql.list_restaurants()]


@router.get("/categories", response_model=list[CategoryOut])
def list_categories() -> list[CategoryOut]:
    return [CategoryOut(**c) for c in sql.list_categories()]
