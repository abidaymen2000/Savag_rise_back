from datetime import datetime
from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, Field, field_validator

DiscountType = Literal["percent", "fixed"]

class PromoBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    description: Optional[str] = None
    discount_type: DiscountType
    amount: float = Field(..., gt=0)
    max_uses: Optional[int] = Field(None, gt=0)
    per_user_limit: Optional[int] = Field(None, gt=0)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    minimum_order_total: Optional[float] = Field(None, ge=0)
    applicable_product_ids: Optional[List[str]] = None
    applicable_category_ids: Optional[List[str]] = None
    stackable: bool = False
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v, info):
        # si percent, 0 < amount <= 100
        discount_type = info.data.get("discount_type")
        if discount_type == "percent" and not (0 < v <= 100):
            raise ValueError("For percent discounts, amount must be in (0, 100].")
        return v

class PromoCreate(PromoBase):
    pass

class PromoUpdate(BaseModel):
    description: Optional[str] = None
    discount_type: Optional[DiscountType] = None
    amount: Optional[float] = Field(None, gt=0)
    max_uses: Optional[int] = Field(None, gt=0)
    per_user_limit: Optional[int] = Field(None, gt=0)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    minimum_order_total: Optional[float] = Field(None, ge=0)
    applicable_product_ids: Optional[List[str]] = None
    applicable_category_ids: Optional[List[str]] = None
    stackable: Optional[bool] = None
    is_active: Optional[bool] = None

class PromoOut(PromoBase):
    id: str
    uses_count: int
    user_uses: Dict[str, int]
    created_at: datetime
    updated_at: datetime

class ApplyRequest(BaseModel):
    code: str
    user_id: Optional[str] = None
    order_total: float
    product_ids: Optional[List[str]] = None
    category_ids: Optional[List[str]] = None

class ApplyResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None
    discounted_total: Optional[float] = None
    discount_value: Optional[float] = None
    code: Optional[str] = None
