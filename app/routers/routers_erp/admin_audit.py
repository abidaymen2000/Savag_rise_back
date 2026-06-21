from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.pagination import PaginatedResponse, PaginationParams, pagination_params
from app.db import get_db
from app.dependencies_admin import require_superadmin
from app.schemas.audit import AuditLogOut
from app.services.services_erp import audit_service


router = APIRouter(prefix="/admin/audit-logs", tags=["admin-audit"])


@router.get("", response_model=PaginatedResponse[AuditLogOut])
async def admin_list_audit_logs(
    _super=Depends(require_superadmin),
    db=Depends(get_db),
    pagination: PaginationParams = Depends(pagination_params),
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    admin_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
):
    return await audit_service.list_logs(db, pagination, module, action, admin_id, entity_type, entity_id)
