from datetime import datetime
from typing import Any, Optional


COLLECTION = "order_status_history"


async def append_history(
    db,
    session=None,
    *,
    order_id: str,
    event_type: str,
    from_order_status: Optional[str] = None,
    to_order_status: Optional[str] = None,
    from_payment_status: Optional[str] = None,
    to_payment_status: Optional[str] = None,
    from_fulfillment_status: Optional[str] = None,
    to_fulfillment_status: Optional[str] = None,
    reason: Optional[str] = None,
    changed_by: Optional[str] = None,
    actor_type: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    doc = {
        "order_id": order_id,
        "event_type": event_type,
        "from_order_status": from_order_status,
        "to_order_status": to_order_status,
        "from_payment_status": from_payment_status,
        "to_payment_status": to_payment_status,
        "from_fulfillment_status": from_fulfillment_status,
        "to_fulfillment_status": to_fulfillment_status,
        "reason": reason,
        "changed_by": changed_by,
        "actor_type": actor_type,
        "metadata": metadata or {},
        "created_at": datetime.utcnow(),
    }
    await db[COLLECTION].insert_one(doc, session=session)
