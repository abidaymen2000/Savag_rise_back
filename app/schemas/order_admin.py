from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OrderNoteIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class OrderNoteOut(BaseModel):
    id: str
    content: str
    admin_id: Optional[str] = None
    admin_email: Optional[str] = None
    created_at: datetime


class OrderTagsIn(BaseModel):
    tags: List[str] = Field(default_factory=list)


class OrderAssignIn(BaseModel):
    admin_id: Optional[str] = None


class OrderTimelineEventOut(BaseModel):
    id: str
    type: str
    message: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    admin_id: Optional[str] = None
    admin_email: Optional[str] = None
    created_at: datetime
