from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.crud import user_admin as user_crud


def parse_oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID utilisateur invalide")


async def list_users(db, page: int, page_size: int, q: Optional[str], is_active: Optional[bool], sort_by: str, sort_dir: str):
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
    items = await user_crud.list_users(db, filters, skip, page_size, (sort_field, direction))
    total = await user_crud.count_users(db, filters)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "sort": {"by": sort_field, "dir": sort_dir},
        "filters": filters,
    }


async def set_user_active(db, user_id: str, active: bool):
    oid = parse_oid(user_id)
    user = await user_crud.get_user(db, oid)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
    if user.get("is_active", True) == active:
        return {"message": "Deja actif" if active else "Deja desactive", "user": user}
    ok = await user_crud.set_user_active(db, oid, active)
    if not ok:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Echec d'activation" if active else "Echec de desactivation")
    user = await user_crud.get_user(db, oid)
    return {"message": "Utilisateur active" if active else "Utilisateur desactive", "user": user}
