# app/utils/discounts.py
from typing import Optional, List, Tuple
from datetime import datetime, timezone

def _to_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalise une datetime en UTC "aware".
    - None -> None
    - naive (tzinfo=None) -> considérée comme UTC
    - aware -> convertie en UTC
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def validate_and_compute(
    promo: dict,
    *,
    user_id: Optional[str],
    order_total: float,
    product_ids: Optional[List[str]],
    category_ids: Optional[List[str]],
) -> Tuple[bool, Optional[str], Optional[float], Optional[float]]:
    # horloge en UTC aware
    now = datetime.now(timezone.utc)

    # dates promo normalisées (évite "can't compare offset-naive and offset-aware datetimes")
    starts_at = _to_utc_aware(promo.get("starts_at"))
    ends_at   = _to_utc_aware(promo.get("ends_at"))

    if not promo.get("is_active", True):
        return False, "inactive", None, None
    if starts_at and now < starts_at:
        return False, "not_started", None, None
    if ends_at and now > ends_at:
        return False, "expired", None, None

    if promo.get("max_uses") is not None and promo.get("uses_count", 0) >= promo["max_uses"]:
        return False, "max_uses_reached", None, None

    # seuil de commande : tester explicitement le None
    min_total = promo.get("minimum_order_total")
    if min_total is not None and order_total < float(min_total):
        return False, "order_total_too_low", None, None

    # périmètre produits / catégories (si définis)
    ap_products = set(promo.get("applicable_product_ids", []) or [])
    ap_categories = set(promo.get("applicable_category_ids", []) or [])

    if ap_products:
        if not product_ids or not ap_products.intersection(set(product_ids)):
            return False, "not_applicable_products", None, None
    if ap_categories:
        if not category_ids or not ap_categories.intersection(set(category_ids)):
            return False, "not_applicable_categories", None, None

    if user_id and promo.get("per_user_limit") is not None:
        used = promo.get("user_uses", {}).get(user_id, 0)
        if used >= promo["per_user_limit"]:
            return False, "per_user_limit_reached", None, None

    # calcul du discount
    if promo["discount_type"] == "percent":
        discount_value = (float(promo["amount"]) / 100.0) * float(order_total)
    else:
        discount_value = float(promo["amount"])

    # on ne descend jamais sous zéro
    discount_value = max(0.0, min(discount_value, float(order_total)))
    discounted_total = float(order_total) - discount_value

    return True, None, discounted_total, discount_value
