from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .utils import PyObjectId


class OrderHistoryDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
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
    created_at: datetime

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str, datetime: lambda dt: dt.isoformat()}
