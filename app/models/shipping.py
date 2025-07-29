# app/models/shipping.py
from pydantic import BaseModel, EmailStr
from typing import Optional

class ShippingDB(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    address_line1: str
    address_line2: Optional[str] = None
    postal_code: str
    city: str
    country: str

    class Config:
        arbitrary_types_allowed = True
