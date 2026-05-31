from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ShippingRateBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    country: str = Field(..., min_length=2, max_length=80)
    city: Optional[str] = Field(None, max_length=80)
    price: float = Field(..., ge=0)
    free_shipping_threshold: Optional[float] = Field(None, ge=0)
    is_active: bool = True


class ShippingRateCreate(ShippingRateBase):
    pass


class ShippingRateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    country: Optional[str] = Field(None, min_length=2, max_length=80)
    city: Optional[str] = Field(None, max_length=80)
    price: Optional[float] = Field(None, ge=0)
    free_shipping_threshold: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ShippingRateOut(ShippingRateBase):
    id: str
    created_at: datetime
    updated_at: datetime


class ShippingQuoteRequest(BaseModel):
    country: str
    city: str
    order_total: float = Field(..., ge=0)


class ShippingQuoteResponse(BaseModel):
    shipping_rate_id: str
    shipping_rate_name: str
    shipping_amount: float
    free_shipping_threshold: Optional[float] = None
