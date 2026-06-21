from fastapi import HTTPException, status

from app.core.pagination import build_page
from app.crud import shipping_rate as shipping_crud


async def create_shipping_rate(db, payload):
    return await shipping_crud.create_shipping_rate(db, payload)


async def list_shipping_rates(db, skip: int, limit: int, is_active):
    return await shipping_crud.list_shipping_rates(db, skip=skip, limit=limit, is_active=is_active)


async def list_shipping_rates_page(db, pagination, is_active):
    filters = {}
    if is_active is not None:
        filters["is_active"] = is_active
    total = await shipping_crud.count_shipping_rates(db, filters)
    items = await shipping_crud.list_shipping_rates(
        db,
        skip=pagination.skip,
        limit=pagination.page_size,
        is_active=is_active,
    )
    return build_page(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        sort={"by": "country,city,name", "dir": "asc"},
        filters={"is_active": is_active},
    )


async def get_shipping_rate(db, rate_id: str):
    rate = await shipping_crud.get_shipping_rate(db, rate_id)
    if not rate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarif de livraison introuvable")
    return rate


async def update_shipping_rate(db, rate_id: str, payload):
    rate = await shipping_crud.update_shipping_rate(db, rate_id, payload)
    if not rate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarif de livraison introuvable")
    return rate


async def delete_shipping_rate(db, rate_id: str) -> None:
    deleted = await shipping_crud.delete_shipping_rate(db, rate_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarif de livraison introuvable")
