from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class OrderHistoryBase(BaseModel):
    order_id: str
    event_type: str
    from_order_status: Optional[str] = None
    to_order_status: Optional[str] = None
    from_payment_status: Optional[str] = None
    to_payment_status: Optional[str] = None
    from_fulfillment_status: Optional[str] = None
    to_fulfillment_status: Optional[str] = None
    reason: Optional[str] = None
    changed_by: Optional[str] = None
    actor_type: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderHistoryRead(OrderHistoryBase):
    id: str
    created_at: datetime
