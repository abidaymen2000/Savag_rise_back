from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies_admin import require_superadmin
from app.schemas.admin import AdminCreate, AdminPasswordReset, AdminPublic, AdminUpdate
from app.services.services_erp import admin_admin_service


router = APIRouter(prefix="/admin/admins", tags=["admin-admins"])


@router.get("", summary="Lister les admins")
async def list_admins(
    _super=Depends(require_superadmin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    return await admin_admin_service.list_admins(page, page_size, q, is_active)


@router.post("", response_model=AdminPublic, status_code=201, summary="Creer un admin")
async def create_admin(payload: AdminCreate, _super=Depends(require_superadmin)):
    return await admin_admin_service.create_admin(payload)


@router.get("/{admin_id}", response_model=AdminPublic, summary="Lire un admin")
async def get_admin(admin_id: str, _super=Depends(require_superadmin)):
    return await admin_admin_service.get_admin(admin_id)


@router.patch("/{admin_id}", response_model=AdminPublic, summary="Modifier un admin")
async def update_admin(admin_id: str, payload: AdminUpdate, current_super=Depends(require_superadmin)):
    return await admin_admin_service.update_admin(admin_id, payload, current_super)


@router.patch("/{admin_id}/password", response_model=AdminPublic, summary="Reinitialiser le mot de passe admin")
async def reset_admin_password(admin_id: str, payload: AdminPasswordReset, _super=Depends(require_superadmin)):
    return await admin_admin_service.reset_password(admin_id, payload)


@router.delete("/{admin_id}", summary="Supprimer un admin")
async def delete_admin(admin_id: str, current_super=Depends(require_superadmin)):
    return await admin_admin_service.delete_admin(admin_id, current_super)
