from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db import get_db
from app.dependencies_admin import get_current_admin
from app.schemas.loyalty import (
    LoyaltyAdjustmentIn,
    LoyaltyBalanceOut,
    LoyaltySettingsOut,
    LoyaltySettingsUpdate,
    LoyaltyTransactionOut,
    PaginatedLoyaltyTransactionsOut,
)
from app.utils.loyalty_service import (
    LOYALTY_SETTINGS_KEY,
    SETTINGS_COLLECTION,
    TRANSACTIONS_COLLECTION,
    add_loyalty_transaction,
    get_points_balance,
    loyalty_settings_out,
    now_utc,
    points_value,
    validate_object_id,
)

router = APIRouter(prefix="/admin/loyalty", tags=["admin-loyalty"])


def _transaction_out(doc) -> LoyaltyTransactionOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    return LoyaltyTransactionOut(**payload)


@router.get("/settings", response_model=LoyaltySettingsOut)
async def admin_get_loyalty_settings(_admin=Depends(get_current_admin), db=Depends(get_db)):
    return await loyalty_settings_out(db)


@router.put("/settings", response_model=LoyaltySettingsOut)
async def admin_update_loyalty_settings(
    payload: LoyaltySettingsUpdate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    value = payload.model_dump()
    updated_at = now_utc()
    await db[SETTINGS_COLLECTION].update_one(
        {"_id": LOYALTY_SETTINGS_KEY},
        {"$set": {"value": value, "updated_at": updated_at}},
        upsert=True,
    )
    return LoyaltySettingsOut(**value, updated_at=updated_at)


@router.get("/users/{user_id}", response_model=LoyaltyBalanceOut)
async def admin_get_user_loyalty(
    user_id: str,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    validate_object_id(user_id, "Utilisateur ID")
    settings = await loyalty_settings_out(db)
    balance = await get_points_balance(db, user_id)
    docs = await db[TRANSACTIONS_COLLECTION].find({"user_id": user_id}).sort("created_at", -1).limit(limit).to_list(length=limit)
    return LoyaltyBalanceOut(
        user_id=user_id,
        points_balance=balance,
        value_balance=points_value(balance, settings),
        settings=settings,
        recent_transactions=[_transaction_out(doc) for doc in docs],
    )


@router.post("/users/{user_id}/adjust", response_model=LoyaltyBalanceOut)
async def admin_adjust_user_loyalty(
    user_id: str,
    payload: LoyaltyAdjustmentIn,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    user_oid = validate_object_id(user_id, "Utilisateur ID")
    user = await db["users"].find_one({"_id": user_oid}, {"loyalty_points_balance": 1})
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
    before = int(user.get("loyalty_points_balance", 0) or 0)
    balance = max(0, before + payload.points)
    delta = balance - before
    await db["users"].update_one(
        {"_id": user_oid},
        {"$set": {"loyalty_points_balance": balance}},
    )
    settings = await loyalty_settings_out(db)
    await add_loyalty_transaction(
        db,
        user_id=user_id,
        tx_type="adjust",
        points=delta,
        value=points_value(abs(delta), settings) * (1 if delta >= 0 else -1),
        balance_after=balance,
        reason=payload.reason or "Ajustement admin",
    )
    docs = await db[TRANSACTIONS_COLLECTION].find({"user_id": user_id}).sort("created_at", -1).limit(20).to_list(length=20)
    return LoyaltyBalanceOut(
        user_id=user_id,
        points_balance=balance,
        value_balance=points_value(balance, settings),
        settings=settings,
        recent_transactions=[_transaction_out(doc) for doc in docs],
    )


@router.get("/transactions", response_model=PaginatedLoyaltyTransactionsOut)
async def admin_list_loyalty_transactions(
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user_id: str | None = Query(None),
    order_id: str | None = Query(None),
):
    filters = {}
    if user_id:
        filters["user_id"] = user_id
    if order_id:
        filters["order_id"] = order_id
    skip = (page - 1) * page_size
    total = await db[TRANSACTIONS_COLLECTION].count_documents(filters)
    docs = await db[TRANSACTIONS_COLLECTION].find(filters).sort("created_at", -1).skip(skip).limit(page_size).to_list(length=page_size)
    return PaginatedLoyaltyTransactionsOut(
        items=[_transaction_out(doc) for doc in docs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )
