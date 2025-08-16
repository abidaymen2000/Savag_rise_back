# app/models/order.py
from bson import ObjectId
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from .shipping import ShippingDB
from .utils import PyObjectId

class OrderDB(BaseModel):
    id: PyObjectId
    user_id: Optional[str]

    # Adresse/expédition
    shipping: ShippingDB
    shipping_address: Optional[str] = None  # (déprécié, gardé pour compat)

    # Lignes de commande
    items: List[dict]  # chaque dict = OrderItem.dict()

    # Paiement
    payment_method: str  # "cod" | "stripe" | "paypal"
    payment_status: str  # "unpaid" | "paid" | "refunded"

    # Remises / totaux
    subtotal: Optional[float] = None       # << NEW (avant remise)
    discount_value: Optional[float] = None # << NEW
    promo_code: Optional[str] = None       # << NEW
    total_amount: float                    # total payé (après remise)

    # Statuts & dates
    status: str  # "pending" | "confirmed" | "shipped" | "delivered" | "cancelled"
    created_at: datetime
    updated_at: datetime

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            PyObjectId: str,
            datetime: lambda dt: dt.isoformat(),
        }
