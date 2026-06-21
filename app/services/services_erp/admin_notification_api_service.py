from typing import Literal, Optional

from fastapi import HTTPException, status, WebSocket
from jose import JWTError, jwt

from app.config import settings
from app.core.pagination import build_page
from app.crud.admin import get_by_email
from app.schemas.notification import NotificationUnreadCount
from app.services.services_erp.notification_service import (
    count_notifications,
    create_notification,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    notification_manager,
)


def admin_id(admin) -> str:
    return str(admin.id)


def status_filter(status_filter: Literal["unread", "read", "all"], admin_id_value: str) -> dict:
    if status_filter == "unread":
        return {"read_by_admin_ids": {"$ne": admin_id_value}}
    if status_filter == "read":
        return {"read_by_admin_ids": admin_id_value}
    return {}


async def list_page(db, current_admin, pagination, status_value, category: Optional[str], priority):
    current_admin_id = admin_id(current_admin)
    filters = status_filter(status_value, current_admin_id)
    if category:
        filters["category"] = category
    if priority:
        filters["priority"] = priority
    items = await list_notifications(db, admin_id=current_admin_id, filters=filters, skip=pagination.skip, limit=pagination.page_size)
    total = await count_notifications(db, admin_id=current_admin_id, filters=filters)
    return build_page(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        sort={"by": "created_at", "dir": "desc"},
        filters={"status": status_value, "category": category, "priority": priority},
    )


async def unread_count(db, current_admin):
    current_admin_id = admin_id(current_admin)
    total = await count_notifications(db, admin_id=current_admin_id, filters={"read_by_admin_ids": {"$ne": current_admin_id}})
    return NotificationUnreadCount(unread_count=total)


async def create(db, payload):
    return await create_notification(db, payload)


async def mark_read(db, notification_id: str, current_admin):
    notification = await mark_notification_read(db, notification_id=notification_id, admin_id=admin_id(current_admin))
    if not notification:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification introuvable")
    return notification


async def mark_all_read(db, current_admin):
    modified = await mark_all_notifications_read(db, admin_id=admin_id(current_admin))
    return {"updated": modified}


async def admin_from_ws_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("scope") != "admin":
            return None
        email = payload.get("sub")
        if not email:
            return None
    except JWTError:
        return None
    admin = await get_by_email(email)
    if not admin or not admin.is_active:
        return None
    return admin


async def websocket_handler(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    admin = await admin_from_ws_token(token)
    if not admin:
        await websocket.close(code=1008)
        return
    current_admin_id = str(admin.id)
    await notification_manager.connect(current_admin_id, websocket)
    try:
        await websocket.send_json({"type": "notification.ready"})
        while True:
            await websocket.receive_text()
    except Exception:
        notification_manager.disconnect(current_admin_id, websocket)
