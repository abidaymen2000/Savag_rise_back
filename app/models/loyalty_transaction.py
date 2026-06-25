from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .utils import PyObjectId


class LoyaltyTransactionDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    user_id: str
    type: str
    points: int
    value: float
    order_id: Optional[str] = None
    reason: Optional[str] = None
    operation_key: Optional[str] = None
    balance_after: int
    created_at: datetime

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str, datetime: lambda dt: dt.isoformat()}
