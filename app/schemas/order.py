from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.config import settings
from app.integrations.meta.schemas import MetaEventContextIn
from app.schemas.pack import PackOrderSelection


ORDER_STATUS_VALUES = Literal[
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

PAYMENT_STATUS_VALUES = Literal["unpaid", "pending", "paid", "failed", "refunded", "partially_refunded"]
FULFILLMENT_STATUS_VALUES = Literal["unfulfilled", "reserved", "processing", "fulfilled", "returning", "returned", "cancelled"]


class ShippingInfo(BaseModel):
    full_name: str = Field(..., example="Jean Dupont")
    email: Optional[EmailStr] = Field(None, example="jean@example.com")
    phone: str = Field(..., example="+216 21 461 637")
    address_line1: str = Field(..., example="12 rue de la Paix")
    address_line2: str | None = Field(None, example="Batiment B, 2e etage")
    postal_code: str = Field(..., example="75001")
    city: str = Field(..., example="Tunis")
    country: str = Field(..., example="Tunisia")


class OrderItemCreate(BaseModel):
    product_id: str
    color: str
    size: str
    qty: int = Field(..., ge=1)


class OrderActionReasonIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=300)


class OrderRefundIn(BaseModel):
    amount: Optional[float] = Field(None, ge=0)
    reason: Optional[str] = Field(None, max_length=300)


class OrderCreate(BaseModel):
    user_id: Optional[str] = None
    items: List[OrderItemCreate] = Field(default_factory=list)
    shipping: ShippingInfo
    payment_method: Literal["cod", "stripe", "paypal"] = "cod"
    promo_code: Optional[str] = None
    loyalty_points_to_use: int = Field(0, ge=0)
    pack_items: List[PackOrderSelection] = Field(default_factory=list)
    meta: Optional[MetaEventContextIn] = None


class InventoryAllocationOut(BaseModel):
    product_id: str
    color: str
    size: str
    qty: int


class OrderQuoteLineOut(BaseModel):
    item_type: Literal["single", "pack_component"]
    product_id: str
    variant_id: str
    sku: Optional[str] = None
    meta_content_id: Optional[str] = None
    product_name: str
    color: str
    size: str
    qty: int
    unit_price_original: float
    unit_price: float
    unit_price_final: float
    discount_amount: float = 0
    line_total: float
    pack_id: Optional[str] = None
    pack_title: Optional[str] = None
    pack_component_id: Optional[str] = None
    stock_available: Optional[int] = None


class OrderPackItemOut(BaseModel):
    component_id: str
    product_id: str
    color: str
    size: str
    qty: int
    unit_price_original: float


class OrderPackQuoteOut(BaseModel):
    pack_id: str
    title: str
    qty: int
    items: List[OrderPackItemOut] = Field(default_factory=list)
    original_amount: float
    discount_amount: float
    final_amount: float


class PromotionQuoteOut(BaseModel):
    code: str
    discount_amount: float


class LoyaltyQuoteSummaryOut(BaseModel):
    points_requested: int
    points_used: int
    discount_amount: float


class OrderQuoteOut(BaseModel):
    currency: str = Field(default=settings.META_CATALOG_CURRENCY)
    subtotal: float
    pack_discount: float
    promotion_discount: float
    loyalty_discount: float
    shipping_amount: float
    total: float
    items: List[OrderQuoteLineOut] = Field(default_factory=list)
    promotion: Optional[PromotionQuoteOut] = None
    loyalty: Optional[LoyaltyQuoteSummaryOut] = None
    warnings: List[str] = Field(default_factory=list)
    shipping_rate_id: Optional[str] = None
    shipping_rate_name: Optional[str] = None
    pack_items: List[OrderPackQuoteOut] = Field(default_factory=list)
    inventory_allocations: List[InventoryAllocationOut] = Field(default_factory=list)
    discount_value: float = 0
    pack_discount_value: float = 0
    promo_code: Optional[str] = None
    promo_discount_value: float = 0
    loyalty_points_used: int = 0
    loyalty_discount_value: float = 0
    total_amount: float
    item_snapshots: List[OrderQuoteLineOut] = Field(default_factory=list)


class OrderOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    user_email: Optional[EmailStr] = None
    is_guest: bool = False
    shipping: ShippingInfo
    items: List[OrderItemCreate] = Field(default_factory=list)
    pack_items: List[OrderPackQuoteOut] = Field(default_factory=list)
    item_snapshots: List[OrderQuoteLineOut] = Field(default_factory=list)
    inventory_allocations: List[InventoryAllocationOut] = Field(default_factory=list)
    payment_method: Literal["cod", "stripe", "paypal"] = "cod"
    payment_status: PAYMENT_STATUS_VALUES
    fulfillment_status: FULFILLMENT_STATUS_VALUES
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
    shipping_amount: Optional[float] = None
    shipping_rate_id: Optional[str] = None
    shipping_rate_name: Optional[str] = None
    total_amount: float
    refunded_amount: float = 0
    status: ORDER_STATUS_VALUES
    order_status: ORDER_STATUS_VALUES
    idempotency_key: Optional[str] = None
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def ensure_status_alias_matches(cls, value: Any):
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        order_status = payload.get("order_status")
        status_value = payload.get("status")
        canonical = order_status or status_value
        if canonical is None:
            return payload
        if order_status and status_value and order_status != status_value:
            raise ValueError("status and order_status must match")
        payload["order_status"] = canonical
        payload["status"] = canonical
        return payload
