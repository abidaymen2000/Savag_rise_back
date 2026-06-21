from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.core.pagination import PaginatedResponse, PaginationParams, pagination_params
from app.db import get_db
from app.dependencies import get_current_user_optional
from app.schemas.product import ProductOut
from app.services.services_store import product_service


router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=List[ProductOut])
async def list_products(skip: int = 0, limit: int = 10, db=Depends(get_db)):
    return await product_service.list_products(db, skip, limit)


@router.get("/page", response_model=PaginatedResponse[ProductOut])
async def list_products_page(
    db=Depends(get_db),
    pagination: PaginationParams = Depends(pagination_params),
    gender: Optional[str] = Query(None),
    in_stock: Optional[bool] = Query(None),
    q: Optional[str] = Query(None, description="Recherche produit"),
):
    return await product_service.list_products_page(db, pagination, gender, in_stock, q)


@router.get(
    "/search",
    response_model=List[ProductOut],
    summary="Recherche plein-texte + filtres + tri + pagination",
)
async def search_products_endpoint(
    request: Request,
    text: Optional[str] = Query(None, description="Terme plein-texte"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    gender: Optional[str] = Query(None),
    color: Optional[str] = Query(None),
    size: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    sort: Optional[str] = Query(None, pattern="^(price|full_name):(asc|desc)$"),
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    return await product_service.search_products(
        db, request, current_user, text, min_price, max_price, gender, color, size, skip, limit, sort
    )


@router.get(
    "/{product_id}",
    response_model=ProductOut,
    summary="Recupere un produit par son ID",
)
async def get_product_endpoint(
    product_id: str,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    return await product_service.get_product_detail(db, product_id, request, current_user)
