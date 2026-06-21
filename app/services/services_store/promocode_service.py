from datetime import datetime, timezone
from typing import Optional, Tuple

from app.crud import promocodes as promo_crud
from app.schemas.promocode import ApplyResponse
from app.services.services_store.discounts import validate_and_compute


def to_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def usage_gates(promo: dict, user_id: Optional[str]) -> Tuple[bool, Optional[str]]:
    now = datetime.now(timezone.utc)
    if not promo.get("is_active", False):
        return False, "inactive"
    starts_at = to_aware_utc(promo.get("starts_at"))
    ends_at = to_aware_utc(promo.get("ends_at"))
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


async def apply_code(db, payload, current_user: Optional[dict]) -> ApplyResponse:
    code = (payload.code or "").strip().upper()
    promo = await promo_crud.get_by_code(db, code)
    if not promo:
        return ApplyResponse(valid=False, reason="not_found")

    user_id: Optional[str] = str(current_user["_id"]) if current_user else None
    ok, why = usage_gates(promo, user_id)
    if not ok:
        return ApplyResponse(valid=False, reason=why)

    valid, reason, discounted_total, discount_value = validate_and_compute(
        promo,
        user_id=user_id,
        order_total=payload.order_total,
        product_ids=payload.product_ids,
        category_ids=payload.category_ids,
    )
    if not valid:
        return ApplyResponse(valid=False, reason=reason)

    return ApplyResponse(
        valid=True,
        code=promo["code"],
        discounted_total=discounted_total,
        discount_value=discount_value,
    )
