from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .utils import PyObjectId


class OutboxEventDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    event_type: str
    aggregate_type: str
    aggregate_id: str
    operation_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str
    attempts: int = 0
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str, datetime: lambda dt: dt.isoformat()}
