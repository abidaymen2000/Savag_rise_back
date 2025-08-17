# app/routers/admin_users.py
from datetime import datetime
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query, HTTPException, Path, status
from bson import ObjectId

from app.db import get_db
from app.dependencies_admin import get_current_admin
from app.crud.user_admin import list_users, count_users, set_user_active, get_user

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

def _parse_oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID utilisateur invalide")

@router.get("/", summary="Lister les utilisateurs (admin)")
async def admin_list_users(
    _admin = Depends(get_current_admin),
    db = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: Optional[str] = Query(None, description="recherche email ou nom (regex, insensible à la casse)"),
    is_active: Optional[bool] = Query(None),
    sort_by: Literal["created_at", "_id", "email"] = "_id",
    sort_dir: Literal["asc", "desc"] = "desc",
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
    direction = -1 if sort_dir == "desc" else 1
    sort_field = "created_at" if sort_by == "created_at" else sort_by

    items = await list_users(db, filters, skip, page_size, (sort_field, direction))
    total = await count_users(db, filters)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "sort": {"by": sort_field, "dir": sort_dir},
        "filters": filters,
    }

@router.patch("/{user_id}/activate", summary="Activer un utilisateur")
async def activate_user(
    user_id: str = Path(...),
    _admin = Depends(get_current_admin),
    db = Depends(get_db),
):
    oid = _parse_oid(user_id)
    user = await get_user(db, oid)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
    if user.get("is_active", True):
        return {"message": "Déjà actif", "user": user}
    ok = await set_user_active(db, oid, True)
    if not ok:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Échec d'activation")
    user = await get_user(db, oid)
    return {"message": "Utilisateur activé", "user": user}

@router.patch("/{user_id}/deactivate", summary="Désactiver un utilisateur")
async def deactivate_user(
    user_id: str = Path(...),
    _admin = Depends(get_current_admin),
    db = Depends(get_db),
):
    oid = _parse_oid(user_id)
    user = await get_user(db, oid)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
    if not user.get("is_active", True):
        return {"message": "Déjà désactivé", "user": user}
    ok = await set_user_active(db, oid, False)
    if not ok:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Échec de désactivation")
    user = await get_user(db, oid)
    return {"message": "Utilisateur désactivé", "user": user}
