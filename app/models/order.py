# app/models/order.py
from bson import ObjectId
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from .shipping import ShippingDB
from .utils import PyObjectId
from .variant import VariantDB  # ou OrderItem

class OrderDB(BaseModel):
    id: PyObjectId
    user_id: Optional[str]
    shipping: ShippingDB 
    items: List[dict]            # chaque dict = OrderItem.dict()
    shipping_address: str
    payment_method: str
    total_amount: float
    status: str
    payment_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            PyObjectId: str,
            datetime: lambda dt: dt.isoformat(),
        }
