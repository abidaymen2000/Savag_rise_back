# app/schemas/order.py
from pydantic import BaseModel, EmailStr, Field
from typing import List, Literal, Optional
from datetime import datetime

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
    items: List[OrderItem]
    shipping: ShippingInfo
    payment_method: Literal["cod", "stripe", "paypal"] = "cod"
    promo_code: Optional[str] = None              # << NEW

class OrderOut(OrderCreate):
    id: str
    subtotal: Optional[float] = None              # << NEW (avant remise)
    discount_value: Optional[float] = None        # << NEW (montant de la remise)
    total_amount: float
    status: Literal["pending", "confirmed", "shipped", "delivered", "cancelled"]
    payment_status: Literal["unpaid", "paid", "refunded"]
    created_at: datetime
    updated_at: datetime
