from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

# Document tel qu’il sera stocké dans Mongo
def promocode_doc(
    *,
    code: str,
    description: Optional[str],
    discount_type: str,         # "percent" | "fixed"
    amount: float,              # % si percent, valeur si fixed
    max_uses: Optional[int],
    per_user_limit: Optional[int],
    starts_at: Optional[datetime],
    ends_at: Optional[datetime],
    minimum_order_total: Optional[float],
    applicable_product_ids: Optional[List[str]],
    applicable_category_ids: Optional[List[str]],
    stackable: bool = False,
    is_active: bool = True,
) -> Dict[str, Any]:
    return {
        "code": code.upper().strip(),
        "description": description,
        "discount_type": discount_type,
        "amount": amount,
        "max_uses": max_uses,
        "per_user_limit": per_user_limit,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "minimum_order_total": minimum_order_total,
        "applicable_product_ids": applicable_product_ids or [],
        "applicable_category_ids": applicable_category_ids or [],
        "stackable": stackable,
        "is_active": is_active,
        # champs techniques
        "uses_count": 0,
        "user_uses": {},         # { user_id(str): int }
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
