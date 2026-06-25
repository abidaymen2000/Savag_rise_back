from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class InventoryMovementBase(BaseModel):
    variant_id: str
    product_id: str
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    pack_id: Optional[str] = None
    movement_type: str
    on_hand_delta: int
    reserved_delta: int
    on_hand_before: Optional[int] = None
    on_hand_after: Optional[int] = None
    reserved_before: Optional[int] = None
    reserved_after: Optional[int] = None
    reason: Optional[str] = None
    source: str
    operation_key: str
    actor_id: Optional[str] = None
    actor_type: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InventoryMovementRead(InventoryMovementBase):
    id: str
    created_at: datetime
