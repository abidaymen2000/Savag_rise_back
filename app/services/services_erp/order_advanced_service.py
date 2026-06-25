from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.crud import order as order_crud
from app.schemas.order_admin import OrderNoteOut, OrderTimelineEventOut
from app.services.services_erp.audit_service import log_action
from app.services.services_erp.admin_order_service import parse_oid


async def get_order_or_404(db, order_id: str):
    order = await order_crud.get_order(db, parse_oid(order_id))
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    return order


async def add_note(db, order_id: str, payload, admin):
    oid = parse_oid(order_id)
    await get_order_or_404(db, order_id)
    note = {
        "id": str(uuid4()),
        "content": payload.content.strip(),
        "admin_id": str(admin.id),
        "admin_email": admin.email,
        "created_at": datetime.utcnow(),
    }
    await order_crud.push_order_field(db, oid, "internal_notes", note)
    await log_action(db, admin=admin, action="order.note.add", module="orders", entity_type="order", entity_id=order_id, message="Note interne ajoutee")
    return OrderNoteOut(**note)


async def set_tags(db, order_id: str, payload, admin):
    oid = parse_oid(order_id)
    await get_order_or_404(db, order_id)
    tags = sorted({tag.strip() for tag in payload.tags if tag.strip()})
    await order_crud.set_order_fields(db, oid, {"tags": tags})
    await log_action(db, admin=admin, action="order.tags.set", module="orders", entity_type="order", entity_id=order_id, metadata={"tags": tags})
    return {"tags": tags}


async def assign_order(db, order_id: str, payload, admin):
    oid = parse_oid(order_id)
    await get_order_or_404(db, order_id)
    await order_crud.set_order_fields(db, oid, {"assigned_admin_id": payload.admin_id})
    await log_action(db, admin=admin, action="order.assign", module="orders", entity_type="order", entity_id=order_id, metadata={"assigned_admin_id": payload.admin_id})
    return {"assigned_admin_id": payload.admin_id}


async def list_timeline(db, order_id: str):
    order = await get_order_or_404(db, order_id)
    return [OrderTimelineEventOut(**event) for event in order.get("timeline", [])]
