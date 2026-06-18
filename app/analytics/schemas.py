from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalyticsEventCreate(BaseModel):
    event_name: Optional[str] = Field(None, description="Nom de l'evenement analytics")
    user_id: Optional[str] = None
    anonymous_id: Optional[str] = None
    session_id: Optional[str] = None
    product_id: Optional[str] = None
    order_id: Optional[str] = None
    source: Optional[str] = None
    utm_campaign: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnalyticsEventRead(BaseModel):
    id: str
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
    created_at: datetime


class AnalyticsMetric(BaseModel):
    label: str
    count: int


class ProductMetric(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    count: int


class AnalyticsOverviewResponse(BaseModel):
    visitors_today: int
    unique_visitors_today: int
    page_views: int
    product_views: int
    notify_me_clicks: int
    add_to_cart: int
    checkout_started: int
    orders_completed: int
    users_with_account: int
    conversion_rate: float
    add_to_cart_rate: float
    checkout_conversion_rate: float


class AnalyticsFunnelStep(BaseModel):
    event_name: str
    count: int
    dropoff_from_previous: Optional[float] = None
    conversion_from_previous: Optional[float] = None


class AnalyticsFunnelResponse(BaseModel):
    steps: List[AnalyticsFunnelStep]


class ProductAnalyticsResponse(BaseModel):
    top_products_viewed: List[ProductMetric]
    top_products_added_to_cart: List[ProductMetric]
    top_products_purchased: List[ProductMetric]


class TrafficSourceAnalyticsResponse(BaseModel):
    sources: List[AnalyticsMetric]
    campaigns: List[AnalyticsMetric] = Field(default_factory=list)

