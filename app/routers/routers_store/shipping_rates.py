from fastapi import APIRouter, Depends

from app.db import get_db
from app.schemas.shipping_rate import ShippingQuoteRequest, ShippingQuoteResponse
from app.services.services_store import shipping_rate_service


router = APIRouter(prefix="/shipping-rates", tags=["shipping-rates"])


@router.post("/quote", response_model=ShippingQuoteResponse)
async def quote_shipping_rate(
    payload: ShippingQuoteRequest,
    db=Depends(get_db),
):
    return await shipping_rate_service.quote_shipping_rate(db, payload)
