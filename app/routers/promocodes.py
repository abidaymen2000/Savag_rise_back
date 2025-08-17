# app/routers/promocodes.py
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from typing import Optional, List, Tuple, Literal
from datetime import datetime, timezone

from app.schemas.promocode import (
    PromoCreate, PromoUpdate, PromoOut, ApplyRequest, ApplyResponse
)
from app.db import get_db
from app.crud import promocodes as crud
from app.utils.discounts import validate_and_compute

# 🔐 Auth
from app.dependencies_admin import get_current_admin            # admin obligatoire pour CRUD
from app.dependencies import get_current_user_optional          # user optionnel pour apply()

router = APIRouter(prefix="/promocodes", tags=["Promo Codes"])

# ---------- Helpers ----------
def to_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _usage_gates(promo: dict, user_id: Optional[str]) -> Tuple[bool, Optional[str]]:
    now = datetime.now(timezone.utc)

    if not promo.get("is_active", False):
        return False, "inactive"

    starts_at = to_aware_utc(promo.get("starts_at"))
    ends_at   = to_aware_utc(promo.get("ends_at"))

    if starts_at and starts_at > now:
        return False, "not_started_yet"
    if ends_at and ends_at < now:
        return False, "expired"

    max_uses = promo.get("max_uses")
    if max_uses is not None and promo.get("uses_count", 0) >= max_uses:
        return False, "max_uses_reached"

    per_user = promo.get("per_user_limit")
    if per_user is not None:
        if not user_id:
            return False, "login_required"
        used = (promo.get("user_uses") or {}).get(str(user_id), 0)
        if used >= per_user:
            return False, "per_user_limit_reached"

    return True, None


# ============================================================
#                   ADMIN: CRUD + STATUS
# ============================================================

@router.post("/", response_model=PromoOut, summary="Créer un code promo (admin)")
async def create_promo(
    data: PromoCreate,
    db = Depends(get_db),
    _admin = Depends(get_current_admin),
):
    existing = await crud.get_by_code(db, data.code)
    if existing:
        raise HTTPException(409, "A promo with this code already exists.")
    doc = await crud.create_promocode(db, data)
    return PromoOut(**doc)

@router.get("/", response_model=List[PromoOut], summary="Lister les codes promo (admin)")
async def list_promos(
    db = Depends(get_db),
    _admin = Depends(get_current_admin),
    skip: int = 0,
    limit: int = Query(50, le=200),
    q: Optional[str] = None,
):
    items = await crud.list_promocodes(db, skip=skip, limit=limit, q=q)
    return [PromoOut(**i) for i in items]

@router.get("/{promo_id}", response_model=PromoOut, summary="Lire un code promo (admin)")
async def get_promo(
    promo_id: str = Path(...),
    db = Depends(get_db),
    _admin = Depends(get_current_admin),
):
    doc = await crud.get_by_id(db, promo_id)
    if not doc:
        raise HTTPException(404, "Promo not found")
    return PromoOut(**doc)

@router.patch("/{promo_id}", response_model=PromoOut, summary="Mettre à jour un code promo (admin)")
async def update_promo(
    promo_id: str,
    data: PromoUpdate,
    db = Depends(get_db),
    _admin = Depends(get_current_admin),
):
    doc = await crud.update_promocode(db, promo_id, data)
    if not doc:
        raise HTTPException(404, "Promo not found")
    return PromoOut(**doc)

@router.delete("/{promo_id}", summary="Supprimer un code promo (admin)")
async def delete_promo(
    promo_id: str,
    db = Depends(get_db),
    _admin = Depends(get_current_admin),
):
    ok = await crud.delete_promocode(db, promo_id)
    if not ok:
        raise HTTPException(404, "Promo not found")
    return {"deleted": True}

# --- Activer / Désactiver ---
@router.patch("/{promo_id}/activate", summary="Activer un code promo (admin)")
async def activate_promocode(
    promo_id: str = Path(...),
    db = Depends(get_db),
    _admin = Depends(get_current_admin),
):
    promo = await crud.set_promocode_active(db, promo_id, True)
    if not promo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Promo not found")
    return {"message": "Code promo activé", "promo": PromoOut(**promo)}

@router.patch("/{promo_id}/deactivate", summary="Désactiver un code promo (admin)")
async def deactivate_promocode(
    promo_id: str = Path(...),
    db = Depends(get_db),
    _admin = Depends(get_current_admin),
):
    promo = await crud.set_promocode_active(db, promo_id, False)
    if not promo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Promo not found")
    return {"message": "Code promo désactivé", "promo": PromoOut(**promo)}

# (Option) endpoint unique:
@router.patch("/{promo_id}/status", summary="Changer le statut actif/inactif (admin)")
async def set_promocode_status(
    promo_id: str = Path(...),
    is_active: bool = Query(..., description="true=activer, false=désactiver"),
    db = Depends(get_db),
    _admin = Depends(get_current_admin),
):
    promo = await crud.set_promocode_active(db, promo_id, is_active)
    if not promo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Promo not found")
    return {"message": "Statut mis à jour", "promo": PromoOut(**promo)}


# ============================================================
#                        PUBLIC: APPLY
# ============================================================

@router.post("/apply", response_model=ApplyResponse, summary="Vérifier/appliquer un code promo (public)")
async def apply_code(
    payload: ApplyRequest,
    db = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),  # optionnel
):
    # 1) récupérer le code
    code = (payload.code or "").strip().upper()
    promo = await crud.get_by_code(db, code)
    if not promo:
        return ApplyResponse(valid=False, reason="not_found")

    # 2) identifiant fiable de l'utilisateur (si connecté)
    user_id: Optional[str] = str(current_user["_id"]) if current_user else None

    # 3) limites d’usage AVANT calcul
    ok, why = _usage_gates(promo, user_id)
    if not ok:
        return ApplyResponse(valid=False, reason=why)

    # 4) éligibilité panier
    valid, reason, discounted_total, discount_value = validate_and_compute(
        promo,
        user_id=user_id,
        order_total=payload.order_total,
        product_ids=payload.product_ids,
        category_ids=payload.category_ids,
    )
    if not valid:
        return ApplyResponse(valid=False, reason=reason)

    # 5) OK
    return ApplyResponse(
        valid=True,
        code=promo["code"],
        discounted_total=discounted_total,
        discount_value=discount_value,
    )
