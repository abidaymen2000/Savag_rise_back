from datetime import datetime
from fastapi import APIRouter, Depends, Query
from typing import Optional, Literal

from app.dependencies_admin import get_current_admin
from app.db import get_db
from app.crud.order import list_orders, count_orders

router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])

@router.get("/", summary="Lister toutes les commandes (admin)")
async def admin_list_orders(
    # auth admin
    _admin = Depends(get_current_admin),
    # pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    # filtres
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    email: Optional[str]  = Query(None, description="Filtrer par email client (exact ou partiel)"),
    date_from: Optional[str] = Query(None, description="ISO date/time (incluse)"),
    date_to: Optional[str]   = Query(None, description="ISO date/time (incluse)"),
    # tri
    sort_by: Literal["created_at", "_id", "total_amount"] = "_id",
    sort_dir: Literal["asc", "desc"] = "desc",
    db = Depends(get_db),
):
    # -- Build filters Mongo
    filters = {}
    if status:
        filters["status"] = status

    if email:
        # si tu stockes l'email dans la commande
        filters["user_email"] = {"$regex": email, "$options": "i"}

    # Filtre par dates: si tu as un champ created_at sinon utilise _id (ObjectId date)
    if date_from or date_to:
        created_q = {}
        if date_from:
            try:
                created_q["$gte"] = datetime.fromisoformat(date_from)
            except Exception:
                pass
        if date_to:
            try:
                created_q["$lte"] = datetime.fromisoformat(date_to)
            except Exception:
                pass
        if created_q:
            # adapte ce champ si tu n'as pas created_at (sinon enlève)
            filters["created_at"] = created_q

    # -- Pagination
    skip = (page - 1) * page_size
    # tri
    direction = -1 if sort_dir == "desc" else 1
    sort_field = "created_at" if sort_by == "created_at" else sort_by

    items = await list_orders(db, filters, skip, page_size, (sort_field, direction))
    total = await count_orders(db, filters)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "sort": {"by": sort_field, "dir": sort_dir},
        "filters": filters,
    }
