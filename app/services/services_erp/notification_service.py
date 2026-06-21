from typing import Any, Dict, List, Optional

from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocket

from app.crud import notification as notification_crud
from app.schemas.notification import NotificationCreate, NotificationOut


NOTIFICATIONS_COLLECTION = notification_crud.COLLECTION


class NotificationConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, admin_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(admin_id, []).append(websocket)

    def disconnect(self, admin_id: str, websocket: WebSocket) -> None:
        sockets = self._connections.get(admin_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets and admin_id in self._connections:
            self._connections.pop(admin_id, None)

    async def broadcast(self, notification: NotificationOut) -> None:
        payload = jsonable_encoder(notification)
        recipients = (
            [notification.recipient_admin_id]
            if notification.recipient_admin_id
            else list(self._connections.keys())
        )
        for admin_id in recipients:
            if not admin_id:
                continue
            for websocket in list(self._connections.get(admin_id, [])):
                try:
                    await websocket.send_json({"type": "notification.created", "notification": payload})
                except Exception:
                    self.disconnect(admin_id, websocket)


notification_manager = NotificationConnectionManager()


def serialize_notification(doc: Dict[str, Any], admin_id: Optional[str] = None) -> NotificationOut:
    read_by = doc.get("read_by_admin_ids") or []
    read_at_by = doc.get("read_at_by_admin_ids") or {}
    is_read = bool(admin_id and admin_id in read_by)
    return NotificationOut(
        id=str(doc["_id"]),
        audience=doc.get("audience", "admin"),
        category=doc["category"],
        title=doc["title"],
        message=doc["message"],
        priority=doc.get("priority", "normal"),
        source_module=doc.get("source_module"),
        action_url=doc.get("action_url"),
        metadata=doc.get("metadata") or {},
        recipient_admin_id=doc.get("recipient_admin_id"),
        is_read=is_read,
        created_at=doc["created_at"],
        read_at=read_at_by.get(admin_id) if admin_id else None,
    )


def notification_visibility_filter(admin_id: str) -> Dict[str, Any]:
    return notification_crud.visibility_filter(admin_id)


async def create_notification(
    db,
    payload: NotificationCreate | Dict[str, Any],
    *,
    broadcast: bool = True,
) -> NotificationOut:
    data = payload.model_dump() if isinstance(payload, NotificationCreate) else dict(payload)
    doc = await notification_crud.insert_notification(db, data)
    notification = serialize_notification(doc)
    if broadcast:
        await notification_manager.broadcast(notification)
    return notification


async def list_notifications(
    db,
    *,
    admin_id: str,
    filters: Dict[str, Any],
    skip: int,
    limit: int,
) -> List[NotificationOut]:
    docs = await notification_crud.list_notifications(
        db,
        admin_id=admin_id,
        filters=filters,
        skip=skip,
        limit=limit,
    )
    return [serialize_notification(doc, admin_id) for doc in docs]


async def count_notifications(db, *, admin_id: str, filters: Dict[str, Any]) -> int:
    return await notification_crud.count_notifications(db, admin_id=admin_id, filters=filters)


async def mark_notification_read(db, *, notification_id: str, admin_id: str) -> Optional[NotificationOut]:
    doc = await notification_crud.mark_notification_read(
        db,
        notification_id=notification_id,
        admin_id=admin_id,
    )
    return serialize_notification(doc, admin_id) if doc else None


async def mark_all_notifications_read(db, *, admin_id: str) -> int:
    return await notification_crud.mark_all_notifications_read(db, admin_id=admin_id)
