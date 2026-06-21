from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.dependencies_admin import require_permission
from app.services.services_erp import admin_order_service


router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])


@router.get("/", summary="Lister toutes les commandes (admin)")
async def admin_list_orders(
    _admin=Depends(require_permission("orders")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    email: Optional[str] = Query(None, description="Filtrer par email client (exact ou partiel)"),
    date_from: Optional[str] = Query(None, description="ISO date/time (incluse)"),
    date_to: Optional[str] = Query(None, description="ISO date/time (incluse)"),
    sort_by: Literal["created_at", "_id", "total_amount"] = "_id",
    sort_dir: Literal["asc", "desc"] = "desc",
    db=Depends(get_db),
):
    return await admin_order_service.list_orders(db, page, page_size, status, email, date_from, date_to, sort_by, sort_dir)
