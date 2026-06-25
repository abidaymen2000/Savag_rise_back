from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InventoryItemOut(BaseModel):
    product_id: str
    product_name: str
    sku: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    stock_on_hand: int
    stock_reserved: int
    stock_available: int
    in_stock: bool = True
    low_stock: bool = False


class InventoryAdjustmentIn(BaseModel):
    product_id: str
    color: str
    size: str
    delta: Optional[int] = None
    new_stock_on_hand: Optional[int] = Field(None, ge=0)
    reason: str = Field(..., min_length=2, max_length=300)


class InventoryMovementOut(BaseModel):
    id: str
    product_id: str
    product_name: Optional[str] = None
    color: str
    size: str
    movement_type: str = "manual_adjustment"
    on_hand_delta: int
    reserved_delta: int
    on_hand_before: int
    on_hand_after: int
    reserved_before: int
    reserved_after: int
    reason: str
    source: str = "manual"
    operation_key: Optional[str] = None
    admin_id: Optional[str] = None
    admin_email: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
