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
    event_category: Optional[str] = None
    page_path: Optional[str] = None
    page_title: Optional[str] = None
    action_target: Optional[str] = None
    device_type: str = "unknown"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    source: str = "direct"
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    has_account: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
