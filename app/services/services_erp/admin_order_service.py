from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.crud import order as order_crud
from app.services.services_store import order_domain_service


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
    order = await order_domain_service.get_order_or_404(db, order_id)
    return order_domain_service._order_doc_to_out(order)


async def confirm_order(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.confirm_order(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def prepare_order(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.prepare_order(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def ship_order(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.ship_order(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def deliver_order(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.deliver_order(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def cancel_order(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.cancel_order(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def mark_paid(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.mark_paid(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def request_return(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.request_return(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def mark_return_in_transit(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.mark_return_in_transit(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def receive_return(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.receive_return(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def restock_returned_items(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.restock_returned_items(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def mark_return_damaged(db, order_id: str, admin, reason: Optional[str] = None):
    return await order_domain_service.mark_return_damaged(db, order_id, actor_type="admin", actor_id=str(admin.id), reason=reason)


async def refund_order(db, order_id: str, admin, amount: Optional[float] = None, reason: Optional[str] = None):
    return await order_domain_service.refund_order(db, order_id, actor_type="admin", actor_id=str(admin.id), amount=amount, reason=reason)
