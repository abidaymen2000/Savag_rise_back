from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


LoyaltyTransactionType = Literal["earn", "redeem", "refund", "adjust"]


class LoyaltySettingsBase(BaseModel):
    is_active: bool = True
    earning_percentage: float = Field(10.0, ge=0, le=100)
    point_value: float = Field(1.0, gt=0)
    min_redeem_points: int = Field(1, ge=1)
    max_redeem_percentage: float = Field(100.0, ge=0, le=100)


class LoyaltySettingsUpdate(LoyaltySettingsBase):
    pass


class LoyaltySettingsOut(LoyaltySettingsBase):
    updated_at: Optional[datetime] = None


class LoyaltyTransactionOut(BaseModel):
    id: str
    user_id: str
    type: LoyaltyTransactionType
    points: int
    value: float
    order_id: Optional[str] = None
    reason: Optional[str] = None
    operation_key: Optional[str] = None
    balance_after: int
    created_at: datetime


class LoyaltyBalanceOut(BaseModel):
    user_id: str
    points_balance: int
    value_balance: float
    settings: LoyaltySettingsOut
    recent_transactions: List[LoyaltyTransactionOut] = Field(default_factory=list)


class LoyaltyQuoteIn(BaseModel):
    order_total: float = Field(..., ge=0)
    points_to_use: int = Field(0, ge=0)


class LoyaltyQuoteOut(BaseModel):
    points_balance: int
    requested_points: int
    usable_points: int
    discount_value: float
    remaining_total: float
    estimated_points_earned: int
    settings: LoyaltySettingsOut


class LoyaltyAdjustmentIn(BaseModel):
    points: int
    reason: Optional[str] = None


class PaginatedLoyaltyTransactionsOut(BaseModel):
    items: List[LoyaltyTransactionOut] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    pages: int
