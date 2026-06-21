from fastapi import APIRouter, Depends

from app.core.pagination import PaginatedResponse, PaginationParams, pagination_params
from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.schemas.product import ProductOut
from app.services.services_erp import category_service


router = APIRouter(prefix="/categories", tags=["admin-categories"])


@router.get("/page", response_model=PaginatedResponse[CategoryOut])
async def read_categories_page(
    db=Depends(get_db),
    pagination: PaginationParams = Depends(pagination_params),
    q: str | None = None,
    _admin=Depends(require_permission("categories")),
):
    return await category_service.list_categories_page(db, pagination, q)


@router.post("/", response_model=CategoryOut, status_code=201)
async def create_new_category(
    payload: CategoryCreate,
    db=Depends(get_db),
    _admin=Depends(require_permission("categories")),
):
    return await category_service.create_category(db, payload)


@router.put("/{category_id}", response_model=CategoryOut)
async def modify_category(
    category_id: str,
    payload: CategoryUpdate,
    db=Depends(get_db),
    _admin=Depends(require_permission("categories")),
):
    return await category_service.update_category(db, category_id, payload)


@router.delete("/{category_id}", status_code=204)
async def remove_category(
    category_id: str,
    db=Depends(get_db),
    _admin=Depends(require_permission("categories")),
):
    await category_service.delete_category(db, category_id)


@router.post(
    "/{category_id}/products/{product_id}",
    response_model=ProductOut,
    summary="Ajoute un produit existant a une categorie existante",
)
async def add_product_to_category(
    category_id: str,
    product_id: str,
    db=Depends(get_db),
    _admin=Depends(require_permission("categories")),
):
    return await category_service.add_product_to_category(db, category_id, product_id)
