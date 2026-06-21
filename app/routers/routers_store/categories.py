from typing import List

from fastapi import APIRouter, Depends, Query

from app.core.pagination import PaginatedResponse, PaginationParams, pagination_params
from app.db import get_db
from app.schemas.category import CategoryOut
from app.schemas.product import ProductOut
from app.services.services_store import category_service


router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/", response_model=List[CategoryOut])
async def read_categories(db=Depends(get_db)):
    return await category_service.list_categories(db)


@router.get("/page", response_model=PaginatedResponse[CategoryOut])
async def read_categories_page(
    db=Depends(get_db),
    pagination: PaginationParams = Depends(pagination_params),
    q: str | None = Query(None),
):
    return await category_service.list_categories_page(db, pagination, q)


@router.get("/{category_id}", response_model=CategoryOut)
async def read_category(category_id: str, db=Depends(get_db)):
    return await category_service.get_category(db, category_id)


@router.get("/{category_name}/products", response_model=List[ProductOut])
async def products_by_category(
    category_name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(get_db),
):
    return await category_service.list_products_by_category(db, category_name, skip, limit)
