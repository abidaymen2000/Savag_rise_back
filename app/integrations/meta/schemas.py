from typing import Any

from pydantic import BaseModel, Field


class MetaEventContext(BaseModel):
    event_id: str | None = None
    event_source_url: str | None = None
    fbp: str | None = None
    fbc: str | None = None
    fbclid: str | None = None
    client_ip_address: str | None = None
    client_user_agent: str | None = None


class MetaEventContextIn(BaseModel):
    event_id: str | None = None
    event_source_url: str | None = None
    fbp: str | None = None
    fbc: str | None = None
    fbclid: str | None = None


class MetaEventData(BaseModel):
    event_name: str
    event_time: int
    event_id: str
    action_source: str = "website"
    event_source_url: str | None = None
    user_data: dict[str, Any]
    custom_data: dict[str, Any] = Field(default_factory=dict)


class MetaEventsRequest(BaseModel):
    data: list[MetaEventData]
    test_event_code: str | None = None
