from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class OutboxEventBase(BaseModel):
    event_type: str
    aggregate_type: str
    aggregate_id: str
    operation_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str
    attempts: int = 0
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None


class OutboxEventRead(OutboxEventBase):
    id: str
    created_at: datetime
    processed_at: Optional[datetime] = None
