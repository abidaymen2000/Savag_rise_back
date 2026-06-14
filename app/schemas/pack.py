from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


PackStatus = Literal["draft", "active", "archived"]
PackDiscountType = Literal["percent", "fixed_amount"]


class PackProductSummary(BaseModel):
    id: str
    name: str
    full_name: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    in_stock: bool = True


class PackBase(BaseModel):
    title: str
    description: Optional[str] = None
    product_ids: List[str] = Field(..., min_length=2)
    discount_type: PackDiscountType = "percent"
    discount_value: float = Field(..., ge=0)
    status: PackStatus = "draft"
    image_url: Optional[str] = None
    order: int = 0
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class PackCreate(PackBase):
    pass


class PackUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    product_ids: Optional[List[str]] = Field(None, min_length=2)
    discount_type: Optional[PackDiscountType] = None
    discount_value: Optional[float] = Field(None, ge=0)
    status: Optional[PackStatus] = None
    image_url: Optional[str] = None
    order: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class PackOut(PackBase):
    id: str
    products: List[PackProductSummary] = Field(default_factory=list)
    original_price: float = 0
    pack_price: float = 0
    savings_value: float = 0
    created_at: datetime
    updated_at: datetime


class PackOrderComponent(BaseModel):
    product_id: str
    color: str
    size: str
    qty: int = Field(1, ge=1)
    unit_price: float = Field(..., ge=0)


class PackOrderSelection(BaseModel):
    pack_id: str
    qty: int = Field(1, ge=1)
    items: List[PackOrderComponent] = Field(..., min_length=2)
