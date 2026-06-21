from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.dependencies_admin import require_permission
from app.services.services_erp import export_service


router = APIRouter(prefix="/admin/exports", tags=["admin-exports"])


@router.get("/inventory.csv")
async def export_inventory(
    _admin=Depends(require_permission("products")),
    db=Depends(get_db),
    q: Optional[str] = Query(None),
    color: Optional[str] = Query(None),
    size: Optional[str] = Query(None),
    low_stock: Optional[bool] = Query(None),
    threshold: int = Query(5, ge=0, le=1000),
):
    return await export_service.export_inventory_csv(db, q, color, size, low_stock, threshold)


@router.get("/orders.csv")
async def export_orders(
    _admin=Depends(require_permission("orders")),
    db=Depends(get_db),
    status: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    filters = {}
    if status:
        filters["status"] = status
    if email:
        filters["user_email"] = {"$regex": email, "$options": "i"}
    if date_from or date_to:
        created_q = {}
        if date_from:
            created_q["$gte"] = datetime.fromisoformat(date_from)
        if date_to:
            created_q["$lte"] = datetime.fromisoformat(date_to)
        filters["created_at"] = created_q
    return await export_service.export_orders_csv(db, filters)


@router.get("/clients.csv")
async def export_clients(_admin=Depends(require_permission("users")), db=Depends(get_db)):
    return await export_service.export_clients_csv(db)
