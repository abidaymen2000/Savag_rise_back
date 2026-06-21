from fastapi import APIRouter, Depends, Response, status

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.services.services_erp import admin_product_service


router = APIRouter(prefix="/products", tags=["admin-products"])


@router.post("/", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    db=Depends(get_db),
    _admin=Depends(require_permission("products")),
):
    return await admin_product_service.create_product(db, product)


@router.put("/{product_id}", response_model=ProductOut, summary="Met a jour un produit existant")
async def update_product_endpoint(
    product_id: str,
    product: ProductUpdate,
    db=Depends(get_db),
    _admin=Depends(require_permission("products")),
):
    return await admin_product_service.update_product(db, product_id, product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprime un produit et ses variantes")
async def delete_product(
    product_id: str,
    db=Depends(get_db),
    _admin=Depends(require_permission("products")),
):
    await admin_product_service.delete_product(db, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
