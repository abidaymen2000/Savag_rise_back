from datetime import datetime
from typing import Optional

from app.core.pagination import build_page
from app.crud import audit as audit_crud
from app.schemas.audit import AuditLogOut


def audit_out(doc) -> AuditLogOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    return AuditLogOut(**payload)


async def log_action(
    db,
    *,
    admin=None,
    action: str,
    module: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    message: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    data = {
        "admin_id": str(admin.id) if admin else None,
        "admin_email": getattr(admin, "email", None) if admin else None,
        "action": action,
        "module": module,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "message": message,
        "metadata": metadata or {},
    }
    res = await audit_crud.insert_audit_log(db, data)
    data["id"] = str(res.inserted_id)
    data["created_at"] = data.get("created_at") or datetime.utcnow()
    return AuditLogOut(**data)


async def list_logs(db, pagination, module=None, action=None, admin_id=None, entity_type=None, entity_id=None):
    filters = {}
    if module:
        filters["module"] = module
    if action:
        filters["action"] = action
    if admin_id:
        filters["admin_id"] = admin_id
    if entity_type:
        filters["entity_type"] = entity_type
    if entity_id:
        filters["entity_id"] = entity_id
    total = await audit_crud.count_audit_logs(db, filters)
    docs = await audit_crud.list_audit_logs(db, filters, pagination.skip, pagination.page_size)
    return build_page(
        items=[audit_out(doc) for doc in docs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        sort={"by": "created_at", "dir": "desc"},
        filters=filters,
    )
