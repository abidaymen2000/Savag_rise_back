from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InventoryItemOut(BaseModel):
    product_id: str
    product_name: str
    sku: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    stock: int
    in_stock: bool = True
    low_stock: bool = False


class InventoryAdjustmentIn(BaseModel):
    product_id: str
    color: str
    size: str
    delta: Optional[int] = None
    new_stock: Optional[int] = Field(None, ge=0)
    reason: str = Field(..., min_length=2, max_length=300)


class InventoryMovementOut(BaseModel):
    id: str
    product_id: str
    product_name: Optional[str] = None
    color: str
    size: str
    previous_stock: int
    new_stock: int
    delta: int
    reason: str
    source: str = "manual"
    admin_id: Optional[str] = None
    admin_email: Optional[str] = None
    created_at: datetime
