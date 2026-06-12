from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.dependencies import get_current_user
from app.schemas.loyalty import LoyaltyBalanceOut, LoyaltyQuoteIn, LoyaltyQuoteOut, LoyaltyTransactionOut
from app.utils.loyalty_service import (
    TRANSACTIONS_COLLECTION,
    calculate_earn_points,
    calculate_redeem,
    get_points_balance,
    loyalty_settings_out,
    points_value,
)

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


def _transaction_out(doc) -> LoyaltyTransactionOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    return LoyaltyTransactionOut(**payload)


@router.get("/me", response_model=LoyaltyBalanceOut)
async def get_my_loyalty_balance(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50),
):
    user_id = str(current_user["_id"])
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


@router.post("/quote", response_model=LoyaltyQuoteOut)
async def quote_loyalty_redemption(
    payload: LoyaltyQuoteIn,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = str(current_user["_id"])
    settings = await loyalty_settings_out(db)
    balance = await get_points_balance(db, user_id)
    usable_points, discount_value = calculate_redeem(
        payload.points_to_use,
        balance,
        payload.order_total,
        settings,
    )
    remaining_total = max(0.0, round(float(payload.order_total) - discount_value, 2))
    return LoyaltyQuoteOut(
        points_balance=balance,
        requested_points=payload.points_to_use,
        usable_points=usable_points,
        discount_value=discount_value,
        remaining_total=remaining_total,
        estimated_points_earned=calculate_earn_points(remaining_total, settings),
        settings=settings,
    )
