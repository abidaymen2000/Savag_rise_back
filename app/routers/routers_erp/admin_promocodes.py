from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query

from app.core.pagination import PaginatedResponse, PaginationParams, pagination_params
from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.promocode import PromoCreate, PromoOut, PromoUpdate
from app.services.services_erp import admin_promocode_service


router = APIRouter(prefix="/promocodes", tags=["admin-promocodes"])


@router.post("/", response_model=PromoOut, summary="Creer un code promo (admin)")
async def create_promo(data: PromoCreate, db=Depends(get_db), _admin=Depends(require_permission("promocodes"))):
    return await admin_promocode_service.create_promo(db, data)


@router.get("/", response_model=List[PromoOut], summary="Lister les codes promo (admin)")
async def list_promos(
    db=Depends(get_db),
    _admin=Depends(require_permission("promocodes")),
    skip: int = 0,
    limit: int = Query(50, le=200),
    q: Optional[str] = None,
):
    return await admin_promocode_service.list_promos(db, skip, limit, q)


@router.get("/page", response_model=PaginatedResponse[PromoOut], summary="Lister les codes promo pagines (admin)")
async def list_promos_page(
    db=Depends(get_db),
    _admin=Depends(require_permission("promocodes")),
    pagination: PaginationParams = Depends(pagination_params),
    q: Optional[str] = None,
):
    return await admin_promocode_service.list_promos_page(db, pagination, q)


@router.get("/{promo_id}", response_model=PromoOut, summary="Lire un code promo (admin)")
async def get_promo(promo_id: str = Path(...), db=Depends(get_db), _admin=Depends(require_permission("promocodes"))):
    return await admin_promocode_service.get_promo(db, promo_id)


@router.patch("/{promo_id}", response_model=PromoOut, summary="Mettre a jour un code promo (admin)")
async def update_promo(promo_id: str, data: PromoUpdate, db=Depends(get_db), _admin=Depends(require_permission("promocodes"))):
    return await admin_promocode_service.update_promo(db, promo_id, data)


@router.delete("/{promo_id}", summary="Supprimer un code promo (admin)")
async def delete_promo(promo_id: str, db=Depends(get_db), _admin=Depends(require_permission("promocodes"))):
    return await admin_promocode_service.delete_promo(db, promo_id)


@router.patch("/{promo_id}/activate", summary="Activer un code promo (admin)")
async def activate_promocode(promo_id: str = Path(...), db=Depends(get_db), _admin=Depends(require_permission("promocodes"))):
    return await admin_promocode_service.set_promo_active(db, promo_id, True, "Code promo active")


@router.patch("/{promo_id}/deactivate", summary="Desactiver un code promo (admin)")
async def deactivate_promocode(promo_id: str = Path(...), db=Depends(get_db), _admin=Depends(require_permission("promocodes"))):
    return await admin_promocode_service.set_promo_active(db, promo_id, False, "Code promo desactive")


@router.patch("/{promo_id}/status", summary="Changer le statut actif/inactif (admin)")
async def set_promocode_status(
    promo_id: str = Path(...),
    is_active: bool = Query(..., description="true=activer, false=desactiver"),
    db=Depends(get_db),
    _admin=Depends(require_permission("promocodes")),
):
    return await admin_promocode_service.set_promo_active(db, promo_id, is_active)
