from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.dependencies import get_current_user
from app.schemas.loyalty import LoyaltyBalanceOut, LoyaltyQuoteIn, LoyaltyQuoteOut, LoyaltyTransactionOut
from app.services.services_store import loyalty_service

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


@router.get("/me", response_model=LoyaltyBalanceOut)
async def get_my_loyalty_balance(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50),
):
    return await loyalty_service.get_user_loyalty_balance(db, str(current_user["_id"]), limit)


@router.post("/quote", response_model=LoyaltyQuoteOut)
async def quote_loyalty_redemption(
    payload: LoyaltyQuoteIn,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await loyalty_service.quote_loyalty_redemption(db, str(current_user["_id"]), payload)
