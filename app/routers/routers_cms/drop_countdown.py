from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.drop_countdown import (
    DropCountdownOut,
    DropCountdownUpdate,
    DropSubscribersPage,
)
from app.services.services_cms import drop_countdown_service


router = APIRouter(tags=["drop-countdown"])


@router.get("/admin/drop-countdown", response_model=DropCountdownOut)
async def admin_get_drop_countdown(
    _admin=Depends(require_permission("drop_countdown")),
    db=Depends(get_db),
):
    return await drop_countdown_service.get_admin_drop(db)


@router.get("/admin/drop-countdown/subscribers", response_model=DropSubscribersPage)
async def admin_list_drop_subscribers(
    _admin=Depends(require_permission("drop_countdown")),
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: Optional[str] = Query(None, description="Recherche email ou nom"),
    current_drop_only: bool = Query(True),
):
    return await drop_countdown_service.list_subscribers(db, page, page_size, q, current_drop_only)


@router.put("/admin/drop-countdown", response_model=DropCountdownOut)
async def admin_update_drop_countdown(
    payload: DropCountdownUpdate,
    _admin=Depends(require_permission("drop_countdown")),
    db=Depends(get_db),
):
    return await drop_countdown_service.update_drop_countdown(db, payload)
