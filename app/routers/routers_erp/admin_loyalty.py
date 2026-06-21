from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.loyalty import (
    LoyaltyAdjustmentIn,
    LoyaltyBalanceOut,
    LoyaltySettingsOut,
    LoyaltySettingsUpdate,
    LoyaltyTransactionOut,
    PaginatedLoyaltyTransactionsOut,
)
from app.services.services_store import loyalty_service

router = APIRouter(prefix="/admin/loyalty", tags=["admin-loyalty"])


@router.get("/settings", response_model=LoyaltySettingsOut)
async def admin_get_loyalty_settings(_admin=Depends(require_permission("loyalty")), db=Depends(get_db)):
    return await loyalty_service.loyalty_settings_out(db)


@router.put("/settings", response_model=LoyaltySettingsOut)
async def admin_update_loyalty_settings(
    payload: LoyaltySettingsUpdate,
    _admin=Depends(require_permission("loyalty")),
    db=Depends(get_db),
):
    return await loyalty_service.update_loyalty_settings(db, payload)


@router.get("/users/{user_id}", response_model=LoyaltyBalanceOut)
async def admin_get_user_loyalty(
    user_id: str,
    _admin=Depends(require_permission("loyalty")),
    db=Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    return await loyalty_service.get_user_loyalty_balance(db, user_id, limit)


@router.post("/users/{user_id}/adjust", response_model=LoyaltyBalanceOut)
async def admin_adjust_user_loyalty(
    user_id: str,
    payload: LoyaltyAdjustmentIn,
    _admin=Depends(require_permission("loyalty")),
    db=Depends(get_db),
):
    return await loyalty_service.adjust_user_loyalty(db, user_id, payload)


@router.get("/transactions", response_model=PaginatedLoyaltyTransactionsOut)
async def admin_list_loyalty_transactions(
    _admin=Depends(require_permission("loyalty")),
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user_id: str | None = Query(None),
    order_id: str | None = Query(None),
):
    return await loyalty_service.list_loyalty_transactions(db, page, page_size, user_id, order_id)
