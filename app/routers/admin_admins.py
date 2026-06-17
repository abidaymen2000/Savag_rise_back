from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.crud import admin as admin_crud
from app.dependencies_admin import admin_capabilities, admin_nav_items, require_superadmin
from app.models.admin import AdminInDB
from app.schemas.admin import AdminCreate, AdminPasswordReset, AdminPublic, AdminUpdate
from app.utils.security_admin import hash_password

router = APIRouter(prefix="/admin/admins", tags=["admin-admins"])


async def _public(admin: AdminInDB) -> AdminPublic:
    return AdminPublic(
        id=str(admin.id),
        email=admin.email,
        full_name=admin.full_name,
        is_active=admin.is_active,
        is_superadmin=admin.is_superadmin,
        permissions=admin.permissions,
        capabilities=await admin_capabilities(admin),
        available_permissions=await admin_crud.list_cms_pages(),
        nav_items=await admin_nav_items(admin),
    )


async def _validate_permissions(permissions: list[str]) -> list[str]:
    allowed = set(await admin_crud.get_permission_keys())
    unknown = sorted(set(permissions) - allowed)
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Permissions inconnues: {', '.join(unknown)}",
        )
    return sorted(set(permissions))


@router.get("", summary="Lister les admins")
async def list_admins(
    _super=Depends(require_superadmin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    filters = {}
    if q:
        filters["$or"] = [
            {"email": {"$regex": q, "$options": "i"}},
            {"full_name": {"$regex": q, "$options": "i"}},
        ]
    if is_active is not None:
        filters["is_active"] = is_active
    skip = (page - 1) * page_size
    items = await admin_crud.list_admins(filters, skip, page_size)
    total = await admin_crud.count_admins(filters)
    return {
        "items": [await _public(admin) for admin in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "available_permissions": await admin_crud.list_cms_pages(),
    }


@router.post("", response_model=AdminPublic, status_code=201, summary="Creer un admin")
async def create_admin(payload: AdminCreate, _super=Depends(require_superadmin)):
    existing = await admin_crud.get_by_email(payload.email)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Admin deja existant")
    permissions = [] if payload.is_superadmin else await _validate_permissions(payload.permissions)
    admin = AdminInDB(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=payload.is_active,
        is_superadmin=payload.is_superadmin,
        permissions=permissions,
    )
    created = await admin_crud.create(admin)
    return await _public(created)


@router.get("/{admin_id}", response_model=AdminPublic, summary="Lire un admin")
async def get_admin(admin_id: str, _super=Depends(require_superadmin)):
    admin = await admin_crud.get_by_id(admin_id)
    if not admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Admin introuvable")
    return await _public(admin)


@router.patch("/{admin_id}", response_model=AdminPublic, summary="Modifier un admin")
async def update_admin(
    admin_id: str,
    payload: AdminUpdate,
    current_super=Depends(require_superadmin),
):
    admin = await admin_crud.get_by_id(admin_id)
    if not admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Admin introuvable")

    data = payload.model_dump(exclude_unset=True)
    if "permissions" in data:
        data["permissions"] = await _validate_permissions(data["permissions"])
    target_is_superadmin = data.get("is_superadmin", admin.is_superadmin)
    if target_is_superadmin:
        data["permissions"] = []
    if admin.id == current_super.id and data.get("is_superadmin") is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Vous ne pouvez pas retirer votre propre role super admin")
    if admin.id == current_super.id and data.get("is_active") is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Vous ne pouvez pas desactiver votre propre compte")

    updated = await admin_crud.update_admin(admin_id, data)
    return await _public(updated)


@router.patch("/{admin_id}/password", response_model=AdminPublic, summary="Reinitialiser le mot de passe admin")
async def reset_admin_password(
    admin_id: str,
    payload: AdminPasswordReset,
    _super=Depends(require_superadmin),
):
    admin = await admin_crud.get_by_id(admin_id)
    if not admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Admin introuvable")
    updated = await admin_crud.update_admin(admin_id, {"password_hash": hash_password(payload.new_password)})
    return await _public(updated)


@router.delete("/{admin_id}", summary="Supprimer un admin")
async def delete_admin(admin_id: str, current_super=Depends(require_superadmin)):
    admin = await admin_crud.get_by_id(admin_id)
    if not admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Admin introuvable")
    if admin.id == current_super.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Vous ne pouvez pas supprimer votre propre compte")
    await admin_crud.delete_admin(admin_id)
    return {"deleted": True}
