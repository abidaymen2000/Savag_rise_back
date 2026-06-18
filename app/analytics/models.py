from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models.utils import PyObjectId


ANALYTICS_EVENTS_COLLECTION = "analytics_events"


class AnalyticsEventModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    event_name: str
    user_id: Optional[str] = None
    anonymous_id: Optional[str] = None
    session_id: Optional[str] = None
    product_id: Optional[str] = None
    order_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    source: str = "direct"
    utm_campaign: Optional[str] = None
    has_account: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}

