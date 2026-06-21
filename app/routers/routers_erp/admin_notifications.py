from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, WebSocket

from app.core.pagination import PaginatedResponse, PaginationParams, pagination_params
from app.db import get_db
from app.dependencies_admin import get_current_admin, require_superadmin
from app.schemas.notification import NotificationCreate, NotificationOut, NotificationUnreadCount
from app.services.services_erp import admin_notification_api_service


router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"])


@router.get("", response_model=PaginatedResponse[NotificationOut])
async def admin_list_notifications(
    current_admin=Depends(get_current_admin),
    db=Depends(get_db),
    pagination: PaginationParams = Depends(pagination_params),
    status_filter: Literal["unread", "read", "all"] = Query("all", alias="status"),
    category: Optional[str] = Query(None),
    priority: Optional[Literal["low", "normal", "high", "urgent"]] = Query(None),
):
    return await admin_notification_api_service.list_page(db, current_admin, pagination, status_filter, category, priority)


@router.get("/unread-count", response_model=NotificationUnreadCount)
async def admin_unread_notifications_count(current_admin=Depends(get_current_admin), db=Depends(get_db)):
    return await admin_notification_api_service.unread_count(db, current_admin)


@router.post("", response_model=NotificationOut, status_code=201)
async def admin_create_notification(payload: NotificationCreate, _super=Depends(require_superadmin), db=Depends(get_db)):
    return await admin_notification_api_service.create(db, payload)


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def admin_mark_notification_read(notification_id: str, current_admin=Depends(get_current_admin), db=Depends(get_db)):
    return await admin_notification_api_service.mark_read(db, notification_id, current_admin)


@router.patch("/read-all")
async def admin_mark_all_notifications_read(current_admin=Depends(get_current_admin), db=Depends(get_db)):
    return await admin_notification_api_service.mark_all_read(db, current_admin)


@router.websocket("/ws")
async def admin_notifications_ws(websocket: WebSocket):
    await admin_notification_api_service.websocket_handler(websocket)
