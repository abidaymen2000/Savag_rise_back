# app/schemas/order.py
from pydantic import BaseModel, EmailStr, Field
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime
from app.schemas.pack import PackOrderSelection

class ShippingInfo(BaseModel):
    full_name: str = Field(..., example="Jean Dupont")
    email: EmailStr = Field(..., example="jean@example.com")
    phone: str = Field(..., example="+216 21 461 637")
    address_line1: str = Field(..., example="12 rue de la Paix")
    address_line2: str | None = Field(None, example="Bâtiment B, 2ᵉ étage")
    postal_code: str = Field(..., example="75001")
    city: str = Field(..., example="Tunis")
    country: str = Field(..., example="Sfax")
    
class OrderItem(BaseModel):
    product_id: str
    color: str
    size: str
    qty: int
    unit_price: float  # on le stocke pour figer le prix à la commande

class OrderCreate(BaseModel):
    user_id: Optional[str] = None
    items: List[OrderItem] = Field(default_factory=list)
    shipping: ShippingInfo
    payment_method: Literal["cod", "stripe", "paypal"] = "cod"
    promo_code: Optional[str] = None              # << NEW
    loyalty_points_to_use: int = Field(0, ge=0)
    pack_items: List[PackOrderSelection] = Field(default_factory=list)

class OrderOut(OrderCreate):
    id: str
    pack_items: List[Dict[str, Any]] = Field(default_factory=list)
    user_email: Optional[EmailStr] = None
    is_guest: bool = False
    subtotal: Optional[float] = None              # << NEW (avant remise)
    discount_value: Optional[float] = None        # << NEW (montant de la remise)
    pack_discount_value: float = 0
    loyalty_points_used: int = 0
    loyalty_discount_value: float = 0
    loyalty_points_earned: int = 0
    loyalty_points_awarded: bool = False
    shipping_amount: Optional[float] = None
    shipping_rate_id: Optional[str] = None
    shipping_rate_name: Optional[str] = None
    total_amount: float
    status: Literal["pending", "confirmed", "shipped", "delivered", "cancelled"]
    payment_status: Literal["unpaid", "paid", "refunded"]
    created_at: datetime
    updated_at: datetime
