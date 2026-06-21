from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.analytics import service
from app.analytics.events import event_catalog
from app.analytics.schemas import (
    AnalyticsEventDefinition,
    AnalyticsEventPageResponse,
    AnalyticsEventRead,
    AnalyticsFunnelResponse,
    AnalyticsOverviewResponse,
    ProductAnalyticsResponse,
    TrafficAllDataResponse,
    TrafficBreakdownResponse,
    TrafficButtonsResponse,
    TrafficDashboardResponse,
    TrafficPagesResponse,
    TrafficRealtimeResponse,
    TrafficSourceAnalyticsResponse,
    TrafficTimeSeriesResponse,
)
from app.db import get_db
from app.dependencies_admin import require_permission

router = APIRouter(tags=["analytics"])


@router.get("/admin/analytics/events/catalog", response_model=list[AnalyticsEventDefinition])
async def admin_analytics_event_catalog(
    _admin=Depends(require_permission("analytics")),
):
    return event_catalog()


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


@router.get("/admin/traffic/dashboard", response_model=TrafficDashboardResponse)
async def admin_traffic_dashboard(
    filters: dict = Depends(_filters),
    interval: str = Query("day", regex="^(day|hour|minute)$"),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.traffic_dashboard(db, filters, interval=interval)


@router.get("/admin/traffic/all-data", response_model=TrafficAllDataResponse)
async def admin_traffic_all_data(
    filters: dict = Depends(_filters),
    interval: str = Query("day", regex="^(day|hour|minute)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.traffic_all_data(
        db,
        filters,
        interval=interval,
        page=page,
        page_size=page_size,
    )


@router.get("/admin/traffic/realtime", response_model=TrafficRealtimeResponse)
async def admin_traffic_realtime(
    filters: dict = Depends(_filters),
    window_minutes: int = Query(1, ge=1, le=1440),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.traffic_realtime(db, filters, window_minutes=window_minutes)


@router.get("/admin/traffic/overview", response_model=AnalyticsOverviewResponse)
async def admin_traffic_overview(
    filters: dict = Depends(_filters),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.overview(db, filters)


@router.get("/admin/traffic/timeseries", response_model=TrafficTimeSeriesResponse)
async def admin_traffic_time_series(
    filters: dict = Depends(_filters),
    metric: str = Query(
        "visitors",
        regex="^(visitors|page_views|product_views|add_to_cart|checkout_started|orders_completed|notify_me_clicks|revenue)$",
    ),
    interval: str = Query("day", regex="^(day|hour|minute)$"),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.time_series(db, filters, metric=metric, interval=interval)


@router.get("/admin/traffic/breakdown", response_model=TrafficBreakdownResponse)
async def admin_traffic_breakdown(
    filters: dict = Depends(_filters),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.traffic_breakdown(db, filters)


@router.get("/admin/traffic/sources", response_model=TrafficSourceAnalyticsResponse)
async def admin_traffic_sources(
    filters: dict = Depends(_filters),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.traffic_sources(db, filters)


@router.get("/admin/traffic/pages", response_model=TrafficPagesResponse)
async def admin_traffic_pages(
    filters: dict = Depends(_filters),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.traffic_pages(db, filters, limit=limit)


@router.get("/admin/traffic/buttons", response_model=TrafficButtonsResponse)
async def admin_traffic_buttons(
    filters: dict = Depends(_filters),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.traffic_buttons(db, filters, limit=limit)


@router.get("/admin/traffic/products", response_model=ProductAnalyticsResponse)
async def admin_traffic_products(
    filters: dict = Depends(_filters),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.product_analytics(db, filters)


@router.get("/admin/traffic/funnel", response_model=AnalyticsFunnelResponse)
async def admin_traffic_funnel(
    filters: dict = Depends(_filters),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.funnel(db, filters)


@router.get("/admin/traffic/recent-events", response_model=list[AnalyticsEventRead])
async def admin_traffic_recent_events(
    filters: dict = Depends(_filters),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.recent_events(db, filters, limit=limit)


@router.get("/admin/traffic/events", response_model=AnalyticsEventPageResponse)
async def admin_traffic_events(
    filters: dict = Depends(_filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db=Depends(get_db),
    _admin=Depends(require_permission("traffic")),
):
    return await service.event_page(db, filters, page=page, page_size=page_size)
