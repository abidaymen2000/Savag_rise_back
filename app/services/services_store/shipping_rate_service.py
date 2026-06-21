from app.crud.shipping_rate import resolve_shipping_rate


async def quote_shipping_rate(db, payload):
    return await resolve_shipping_rate(
        db,
        country=payload.country,
        city=payload.city,
        order_total=payload.order_total,
    )
