from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.pagination import PaginatedResponse, PaginationParams, pagination_params
from app.db import get_db
from app.dependencies_admin import get_current_admin, require_permission
from app.schemas.inventory import InventoryAdjustmentIn, InventoryItemOut, InventoryMovementOut
from app.services.services_erp import inventory_service


router = APIRouter(prefix="/admin/inventory", tags=["admin-inventory"])


@router.get("", response_model=PaginatedResponse[InventoryItemOut])
async def admin_list_inventory(
    _admin=Depends(require_permission("products")),
    db=Depends(get_db),
    pagination: PaginationParams = Depends(pagination_params),
    q: Optional[str] = Query(None),
    color: Optional[str] = Query(None),
    size: Optional[str] = Query(None),
    low_stock: Optional[bool] = Query(None),
    threshold: int = Query(5, ge=0, le=1000),
):
    return await inventory_service.list_inventory(db, pagination, q, color, size, low_stock, threshold)


@router.post("/adjust", response_model=InventoryMovementOut, status_code=201)
async def admin_adjust_inventory(
    payload: InventoryAdjustmentIn,
    db=Depends(get_db),
    current_admin=Depends(get_current_admin),
    _permission=Depends(require_permission("products")),
):
    return await inventory_service.adjust_stock(db, payload, current_admin)


@router.get("/movements", response_model=PaginatedResponse[InventoryMovementOut])
async def admin_list_inventory_movements(
    _admin=Depends(require_permission("products")),
    db=Depends(get_db),
    pagination: PaginationParams = Depends(pagination_params),
    product_id: Optional[str] = Query(None),
    color: Optional[str] = Query(None),
    size: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    return await inventory_service.list_movements(db, pagination, product_id, color, size, source)
