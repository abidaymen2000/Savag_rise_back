from fastapi import APIRouter, Depends

from app.db import get_db
from app.dependencies_admin import get_current_admin
from app.services.services_erp.dashboard_service import build_dashboard_summary


router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


@router.get("")
async def admin_dashboard_summary(
    db=Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    return await build_dashboard_summary(db, current_admin)
