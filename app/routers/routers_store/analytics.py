from fastapi import APIRouter, Depends, Request

from app.analytics import service
from app.analytics.events import event_catalog
from app.analytics.schemas import AnalyticsEventCreate, AnalyticsEventDefinition
from app.analytics.utils import get_client_ip, is_allowed_event, rate_limit_allows
from app.db import get_db
from app.dependencies import get_current_user_optional


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
    for key in ("source", "utm_source", "utm_medium", "utm_campaign", "page_path", "page_title", "action_target"):
        value = getattr(payload, key)
        if value and key not in metadata:
            metadata[key] = value

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
    return {
        "success": True,
        "tracked": tracked is not None,
        "event": service.event_to_read(tracked) if tracked else None,
    }


@router.get("/analytics/events/catalog", response_model=list[AnalyticsEventDefinition])
async def analytics_event_catalog():
    return event_catalog()
