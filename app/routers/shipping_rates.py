from fastapi import APIRouter, Depends

from app.crud.shipping_rate import resolve_shipping_rate
from app.db import get_db
from app.schemas.shipping_rate import ShippingQuoteRequest, ShippingQuoteResponse


router = APIRouter(prefix="/shipping-rates", tags=["shipping-rates"])


@router.post("/quote", response_model=ShippingQuoteResponse)
async def quote_shipping_rate(
    payload: ShippingQuoteRequest,
    db=Depends(get_db),
):
    return await resolve_shipping_rate(
        db,
        country=payload.country,
        city=payload.city,
        order_total=payload.order_total,
    )
