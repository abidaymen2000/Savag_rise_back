from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


NotificationAudience = Literal["admin", "erp", "cms", "store"]
NotificationPriority = Literal["low", "normal", "high", "urgent"]
NotificationStatus = Literal["unread", "read", "all"]


class NotificationCreate(BaseModel):
    audience: NotificationAudience = "admin"
    category: str = Field(..., min_length=2, max_length=80)
    title: str = Field(..., min_length=2, max_length=160)
    message: str = Field(..., min_length=2, max_length=500)
    priority: NotificationPriority = "normal"
    source_module: Optional[str] = Field(None, max_length=80)
    action_url: Optional[str] = Field(None, max_length=300)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    recipient_admin_id: Optional[str] = None


class NotificationOut(BaseModel):
    id: str
    audience: NotificationAudience = "admin"
    category: str
    title: str
    message: str
    priority: NotificationPriority = "normal"
    source_module: Optional[str] = None
    action_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    recipient_admin_id: Optional[str] = None
    is_read: bool = False
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationUnreadCount(BaseModel):
    unread_count: int
