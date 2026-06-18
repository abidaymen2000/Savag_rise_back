from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.analytics import service
from app.analytics.schemas import (
    AnalyticsEventCreate,
    AnalyticsEventRead,
    AnalyticsFunnelResponse,
    AnalyticsOverviewResponse,
    ProductAnalyticsResponse,
    TrafficSourceAnalyticsResponse,
)
from app.analytics.utils import get_client_ip, is_allowed_event, rate_limit_allows
from app.db import get_db
from app.dependencies import get_current_user_optional
from app.dependencies_admin import require_permission

router = APIRouter(tags=["analytics"])


@router.post("/analytics/events", summary="Recevoir un evenement analytics public")
async def create_analytics_event(
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    client_ip = get_client_ip(request)
    if not rate_limit_allows(client_ip):
        return {"success": True, "tracked": False, "reason": "rate_limited"}

    try:
        raw_payload = await request.json()
        payload = AnalyticsEventCreate(**raw_payload)
    except Exception:
        return {"success": True, "tracked": False, "reason": "invalid_payload"}

    if not is_allowed_event(payload.event_name):
        return {"success": True, "tracked": False, "reason": "invalid_event_name"}

    user_id = payload.user_id or (str(current_user["_id"]) if current_user else None)
    metadata = dict(payload.metadata or {})
    if payload.source and "source" not in metadata:
        metadata["source"] = payload.source
    if payload.utm_campaign and "utm_campaign" not in metadata:
        metadata["utm_campaign"] = payload.utm_campaign

    tracked = await service.track_event(
        db,
        payload.event_name,
        user_id=user_id,
        anonymous_id=payload.anonymous_id,
        session_id=payload.session_id,
        product_id=payload.product_id,
        order_id=payload.order_id,
        metadata=metadata,
        request=request,
    )
    return {"success": True, "tracked": tracked is not None}


def _filters(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    event_name: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    utm_campaign: Optional[str] = Query(None),
) -> dict:
    return service.build_filters(date_from, date_to, event_name, product_id, source, utm_campaign)


@router.get("/admin/analytics/overview", response_model=AnalyticsOverviewResponse)
async def admin_analytics_overview(
    filters: dict = Depends(_filters),
    db=Depends(get_db),
    _admin=Depends(require_permission("analytics")),
):
    return await service.overview(db, filters)


@router.get("/admin/analytics/funnel", response_model=AnalyticsFunnelResponse)
async def admin_analytics_funnel(
    filters: dict = Depends(_filters),
    db=Depends(get_db),
    _admin=Depends(require_permission("analytics")),
):
    return await service.funnel(db, filters)


@router.get("/admin/analytics/products", response_model=ProductAnalyticsResponse)
async def admin_analytics_products(
    filters: dict = Depends(_filters),
    db=Depends(get_db),
    _admin=Depends(require_permission("analytics")),
):
    return await service.product_analytics(db, filters)


@router.get("/admin/analytics/traffic-sources", response_model=TrafficSourceAnalyticsResponse)
async def admin_analytics_traffic_sources(
    filters: dict = Depends(_filters),
    db=Depends(get_db),
    _admin=Depends(require_permission("analytics")),
):
    return await service.traffic_sources(db, filters)


@router.get("/admin/analytics/recent-events", response_model=list[AnalyticsEventRead])
async def admin_analytics_recent_events(
    filters: dict = Depends(_filters),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    _admin=Depends(require_permission("analytics")),
):
    return await service.recent_events(db, filters, limit=limit)

