from typing import Literal, Optional

from fastapi import APIRouter, Depends, Path, Query

from app.db import get_db
from app.dependencies_admin import require_permission
from app.services.services_erp import admin_user_service


router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("/", summary="Lister les utilisateurs (admin)")
async def admin_list_users(
    _admin=Depends(require_permission("users")),
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: Optional[str] = Query(None, description="recherche email ou nom"),
    is_active: Optional[bool] = Query(None),
    sort_by: Literal["created_at", "_id", "email"] = "_id",
    sort_dir: Literal["asc", "desc"] = "desc",
):
    return await admin_user_service.list_users(db, page, page_size, q, is_active, sort_by, sort_dir)


@router.patch("/{user_id}/activate", summary="Activer un utilisateur")
async def activate_user(
    user_id: str = Path(...),
    _admin=Depends(require_permission("users")),
    db=Depends(get_db),
):
    return await admin_user_service.set_user_active(db, user_id, True)


@router.patch("/{user_id}/deactivate", summary="Desactiver un utilisateur")
async def deactivate_user(
    user_id: str = Path(...),
    _admin=Depends(require_permission("users")),
    db=Depends(get_db),
):
    return await admin_user_service.set_user_active(db, user_id, False)
