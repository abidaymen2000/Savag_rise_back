from fastapi import HTTPException, status

from app.core.pagination import build_page
from app.crud import promocodes as promo_crud
from app.schemas.promocode import PromoOut


async def create_promo(db, data):
    existing = await promo_crud.get_by_code(db, data.code)
    if existing:
        raise HTTPException(409, "A promo with this code already exists.")
    doc = await promo_crud.create_promocode(db, data)
    return PromoOut(**doc)


async def list_promos(db, skip: int, limit: int, q):
    items = await promo_crud.list_promocodes(db, skip=skip, limit=limit, q=q)
    return [PromoOut(**item) for item in items]


async def list_promos_page(db, pagination, q):
    items = await promo_crud.list_promocodes(db, skip=pagination.skip, limit=pagination.page_size, q=q)
    total = await promo_crud.count_promocodes(db, q=q)
    return build_page(
        items=[PromoOut(**item) for item in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        sort={"by": "created_at", "dir": "desc"},
        filters={"q": q},
    )


async def get_promo(db, promo_id: str):
    doc = await promo_crud.get_by_id(db, promo_id)
    if not doc:
        raise HTTPException(404, "Promo not found")
    return PromoOut(**doc)


async def update_promo(db, promo_id: str, data):
    doc = await promo_crud.update_promocode(db, promo_id, data)
    if not doc:
        raise HTTPException(404, "Promo not found")
    return PromoOut(**doc)


async def delete_promo(db, promo_id: str):
    ok = await promo_crud.delete_promocode(db, promo_id)
    if not ok:
        raise HTTPException(404, "Promo not found")
    return {"deleted": True}


async def set_promo_active(db, promo_id: str, is_active: bool, message: str = "Statut mis a jour"):
    promo = await promo_crud.set_promocode_active(db, promo_id, is_active)
    if not promo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Promo not found")
    return {"message": message, "promo": PromoOut(**promo)}
