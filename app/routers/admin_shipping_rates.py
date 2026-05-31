from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.crud.shipping_rate import (
    create_shipping_rate,
    delete_shipping_rate,
    get_shipping_rate,
    list_shipping_rates,
    update_shipping_rate,
)
from app.db import get_db
from app.dependencies_admin import get_current_admin
from app.schemas.shipping_rate import ShippingRateCreate, ShippingRateOut, ShippingRateUpdate


router = APIRouter(prefix="/admin/shipping-rates", tags=["admin-shipping-rates"])


@router.post("/", response_model=ShippingRateOut, status_code=status.HTTP_201_CREATED)
async def admin_create_shipping_rate(
    payload: ShippingRateCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return await create_shipping_rate(db, payload)


@router.get("/", response_model=List[ShippingRateOut])
async def admin_list_shipping_rates(
    db=Depends(get_db),
    _admin=Depends(get_current_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    is_active: Optional[bool] = None,
):
    return await list_shipping_rates(db, skip=skip, limit=limit, is_active=is_active)


@router.get("/{rate_id}", response_model=ShippingRateOut)
async def admin_get_shipping_rate(
    rate_id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_admin),
):
    rate = await get_shipping_rate(db, rate_id)
    if not rate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarif de livraison introuvable")
    return rate


@router.patch("/{rate_id}", response_model=ShippingRateOut)
async def admin_update_shipping_rate(
    rate_id: str,
    payload: ShippingRateUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_admin),
):
    rate = await update_shipping_rate(db, rate_id, payload)
    if not rate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarif de livraison introuvable")
    return rate


@router.delete("/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_shipping_rate(
    rate_id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_admin),
):
    deleted = await delete_shipping_rate(db, rate_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarif de livraison introuvable")
    return None
