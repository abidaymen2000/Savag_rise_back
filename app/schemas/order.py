# app/schemas/order.py
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.pack import PackOrderSelection


class ShippingInfo(BaseModel):
    full_name: str = Field(..., example="Jean Dupont")
    email: EmailStr = Field(..., example="jean@example.com")
    phone: str = Field(..., example="+216 21 461 637")
    address_line1: str = Field(..., example="12 rue de la Paix")
    address_line2: str | None = Field(None, example="Batiment B, 2e etage")
    postal_code: str = Field(..., example="75001")
    city: str = Field(..., example="Tunis")
    country: str = Field(..., example="Sfax")


class OrderItem(BaseModel):
    product_id: str
    color: str
    size: str
    qty: int
    unit_price: float


class OrderActionReasonIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=300)


class OrderRefundIn(BaseModel):
    amount: Optional[float] = Field(None, ge=0)
    reason: Optional[str] = Field(None, max_length=300)


class OrderCreate(BaseModel):
    user_id: Optional[str] = None
    items: List[OrderItem] = Field(default_factory=list)
    shipping: ShippingInfo
    payment_method: Literal["cod", "stripe", "paypal"] = "cod"
    promo_code: Optional[str] = None
    loyalty_points_to_use: int = Field(0, ge=0)
    pack_items: List[PackOrderSelection] = Field(default_factory=list)


class OrderOut(OrderCreate):
    id: str
    idempotency_key: Optional[str] = None
    pack_items: List[Dict[str, Any]] = Field(default_factory=list)
    item_snapshots: List[Dict[str, Any]] = Field(default_factory=list)
    inventory_allocations: List[Dict[str, Any]] = Field(default_factory=list)
    user_email: Optional[EmailStr] = None
    is_guest: bool = False
    subtotal: Optional[float] = None
    discount_value: Optional[float] = None
    pack_discount_value: float = 0
    loyalty_points_used: int = 0
    loyalty_discount_value: float = 0
    loyalty_points_earned: int = 0
    loyalty_points_awarded: bool = False
    shipping_amount: Optional[float] = None
    shipping_rate_id: Optional[str] = None
    shipping_rate_name: Optional[str] = None
    total_amount: float
    status: Literal[
        "pending",
        "confirmed",
        "preparing",
        "shipped",
        "delivered",
        "cancelled",
        "return_requested",
        "return_in_transit",
        "return_received",
        "returned",
    ]
    order_status: Literal[
        "pending",
        "confirmed",
        "preparing",
        "shipped",
        "delivered",
        "cancelled",
        "return_requested",
        "return_in_transit",
        "return_received",
        "returned",
    ]
    payment_status: Literal["unpaid", "pending", "paid", "failed", "refunded", "partially_refunded"]
    fulfillment_status: Literal["unfulfilled", "reserved", "processing", "fulfilled", "returning", "returned", "cancelled"]
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None
    refunded_amount: float = 0
    created_at: datetime
    updated_at: datetime
