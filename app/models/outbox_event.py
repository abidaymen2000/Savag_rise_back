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
    provider: Optional[str] = None
    event_name: Optional[str] = None
    event_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    payload_json: dict[str, Any] = Field(default_factory=dict)
    status: str
    attempts: int = 0
    max_attempts: int = 0
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    last_attempted_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str, datetime: lambda dt: dt.isoformat()}
