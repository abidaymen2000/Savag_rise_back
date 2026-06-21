from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, Request, status

from app.analytics.service import track_event
from app.crud import order as order_crud
from app.services.services_store.loyalty_service import award_points_for_paid_order


def parse_oid(order_id: str) -> ObjectId:
    try:
        return ObjectId(order_id)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID de commande invalide")


async def list_orders(db, page: int, page_size: int, status_value: Optional[str], email: Optional[str], date_from: Optional[str], date_to: Optional[str], sort_by: str, sort_dir: str):
    filters = {}
    if status_value:
        filters["status"] = status_value
    if email:
        filters["user_email"] = {"$regex": email, "$options": "i"}
    if date_from or date_to:
        created_q = {}
        if date_from:
            try:
                created_q["$gte"] = datetime.fromisoformat(date_from)
            except Exception:
                pass
        if date_to:
            try:
                created_q["$lte"] = datetime.fromisoformat(date_to)
            except Exception:
                pass
        if created_q:
            filters["created_at"] = created_q

    skip = (page - 1) * page_size
    direction = -1 if sort_dir == "desc" else 1
    sort_field = "created_at" if sort_by == "created_at" else sort_by
    items = await order_crud.list_orders(db, filters, skip, page_size, (sort_field, direction))
    total = await order_crud.count_orders(db, filters)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "sort": {"by": sort_field, "dir": sort_dir},
        "filters": filters,
    }


async def get_order(db, order_id: str):
    order = await order_crud.get_order(db, parse_oid(order_id))
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    return order


async def update_status(db, order_id: str, new_status: str):
    await order_crud.update_order_status(db, parse_oid(order_id), new_status)
    return {"message": "Statut mis a jour"}


async def mark_paid(db, order_id: str, request: Request):
    oid = parse_oid(order_id)
    await order_crud.mark_paid(db, oid)
    earned_points = await award_points_for_paid_order(db, oid)
    await track_event(
        db,
        "payment_success",
        order_id=order_id,
        metadata={"loyalty_points_earned": earned_points},
        request=request,
    )
    return {"message": "Paiement enregistre", "loyalty_points_earned": earned_points}
