from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from .shipping import ShippingDB
from .utils import PyObjectId


class OrderDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    is_guest: bool = False
    shipping: ShippingDB
    items: List[dict] = Field(default_factory=list)
    pack_items: List[dict] = Field(default_factory=list)
    item_snapshots: List[dict] = Field(default_factory=list)
    inventory_allocations: List[dict] = Field(default_factory=list)
    payment_method: str
    payment_status: str
    fulfillment_status: str
    subtotal: Optional[float] = None
    discount_value: Optional[float] = None
    pack_discount_value: float = 0
    promo_code: Optional[str] = None
    loyalty_points_to_use: int = 0
    loyalty_points_used: int = 0
    loyalty_discount_value: float = 0
    loyalty_eligible_amount: float = 0
    loyalty_points_earned: int = 0
    loyalty_points_awarded: bool = False
    loyalty_points_refunded: bool = False
    shipping_amount: float = 0
    shipping_rate_id: Optional[str] = None
    shipping_rate_name: Optional[str] = None
    total_amount: float
    refunded_amount: float = 0
    meta_context: Optional[dict[str, Any]] = None
    status: str
    order_status: str
    idempotency_key: Optional[str] = None
    payload_hash: Optional[str] = None
    payment_reference: Optional[str] = None
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            PyObjectId: str,
            datetime: lambda dt: dt.isoformat(),
        }
