from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PaginatedResponse, pagination_params, PaginationParams
from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.shipping_rate import ShippingRateCreate, ShippingRateOut, ShippingRateUpdate
from app.services.services_erp import shipping_rate_service


router = APIRouter(prefix="/admin/shipping-rates", tags=["admin-shipping-rates"])


@router.post("/", response_model=ShippingRateOut, status_code=status.HTTP_201_CREATED)
async def admin_create_shipping_rate(
    payload: ShippingRateCreate,
    db=Depends(get_db),
    _admin=Depends(require_permission("shipping")),
):
    return await shipping_rate_service.create_shipping_rate(db, payload)


@router.get("/", response_model=List[ShippingRateOut])
async def admin_list_shipping_rates(
    db=Depends(get_db),
    _admin=Depends(require_permission("shipping")),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    is_active: Optional[bool] = None,
):
    return await shipping_rate_service.list_shipping_rates(db, skip, limit, is_active)


@router.get("/page", response_model=PaginatedResponse[ShippingRateOut])
async def admin_list_shipping_rates_page(
    db=Depends(get_db),
    _admin=Depends(require_permission("shipping")),
    pagination: PaginationParams = Depends(pagination_params),
    is_active: Optional[bool] = None,
):
    return await shipping_rate_service.list_shipping_rates_page(db, pagination, is_active)


@router.get("/{rate_id}", response_model=ShippingRateOut)
async def admin_get_shipping_rate(
    rate_id: str,
    db=Depends(get_db),
    _admin=Depends(require_permission("shipping")),
):
    return await shipping_rate_service.get_shipping_rate(db, rate_id)


@router.patch("/{rate_id}", response_model=ShippingRateOut)
async def admin_update_shipping_rate(
    rate_id: str,
    payload: ShippingRateUpdate,
    db=Depends(get_db),
    _admin=Depends(require_permission("shipping")),
):
    return await shipping_rate_service.update_shipping_rate(db, rate_id, payload)


@router.delete("/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_shipping_rate(
    rate_id: str,
    db=Depends(get_db),
    _admin=Depends(require_permission("shipping")),
):
    await shipping_rate_service.delete_shipping_rate(db, rate_id)
    return None
