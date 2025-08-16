from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Tuple
from datetime import datetime, timezone

from app.schemas.promocode import (
    PromoCreate, PromoUpdate, PromoOut, ApplyRequest, ApplyResponse
)
from app.dependencies import get_db
from app.crud import promocodes as crud
from app.utils.discounts import validate_and_compute

# ⬅️ NOUVEAU : dépendance "optionnelle" pour récupérer l'utilisateur si connecté,
# sans lever d'erreur si anonyme (voir snippet à ajouter dans app/dependencies.py)
from app.dependencies import get_current_user_optional     # type: ignore

router = APIRouter(prefix="/promocodes", tags=["Promo Codes"])


# ---------- Admin: CRUD ----------
@router.post("/", response_model=PromoOut)
async def create_promo(data: PromoCreate, db=Depends(get_db)):
    existing = await crud.get_by_code(db, data.code)
    if existing:
        raise HTTPException(409, "A promo with this code already exists.")
    doc = await crud.create_promocode(db, data)
    return PromoOut(**{**doc, "id": str(doc["_id"])})

@router.get("/", response_model=List[PromoOut])
async def list_promos(
    db=Depends(get_db),
    skip: int = 0,
    limit: int = Query(50, le=200),
    q: Optional[str] = None,
):
    items = await crud.list_promocodes(db, skip=skip, limit=limit, q=q)
    return [PromoOut(**i) for i in items]

@router.get("/{promo_id}", response_model=PromoOut)
async def get_promo(promo_id: str, db=Depends(get_db)):
    doc = await crud.get_by_id(db, promo_id)
    if not doc:
        raise HTTPException(404, "Promo not found")
    return PromoOut(**doc)

@router.patch("/{promo_id}", response_model=PromoOut)
async def update_promo(promo_id: str, data: PromoUpdate, db=Depends(get_db)):
    doc = await crud.update_promocode(db, promo_id, data)
    if not doc:
        raise HTTPException(404, "Promo not found")
    return PromoOut(**doc)

@router.delete("/{promo_id}")
async def delete_promo(promo_id: str, db=Depends(get_db)):
    ok = await crud.delete_promocode(db, promo_id)
    if not ok:
        raise HTTPException(404, "Promo not found")
    return {"deleted": True}


# ---------- Public: appliquer / valider ----------
def to_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Force un datetime en UTC 'aware' (assume UTC si naïf)."""
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


@router.post("/apply", response_model=ApplyResponse)
async def apply_code(
    payload: ApplyRequest,
    db=Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),  # ✅ optionnel
):
    # 1) récupérer le code
    code = (payload.code or "").strip().upper()
    promo = await crud.get_by_code(db, code)
    if not promo:
        return ApplyResponse(valid=False, reason="not_found")

    # 2) identifiant *fiable* de l'utilisateur (si connecté)
    user_id: Optional[str] = str(current_user["_id"]) if current_user else None
    # (on ignore payload.user_id pour éviter la triche côté client)

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