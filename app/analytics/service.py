import logging
from datetime import datetime, time, timedelta
from typing import Any, Dict, Iterable, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.analytics.models import ANALYTICS_EVENTS_COLLECTION
from app.analytics.utils import (
    derive_source,
    extract_utm_campaign,
    is_allowed_event,
    request_metadata,
)

logger = logging.getLogger("analytics")


def _clean_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date_filter(date_from: Optional[datetime], date_to: Optional[datetime]) -> dict:
    created_at = {}
    if date_from:
        created_at["$gte"] = datetime.combine(date_from.date(), time.min) if isinstance(date_from, datetime) else date_from
    if date_to:
        created_at["$lte"] = datetime.combine(date_to.date(), time.max) if isinstance(date_to, datetime) else date_to
    return {"created_at": created_at} if created_at else {}


def build_filters(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    event_name: Optional[str] = None,
    product_id: Optional[str] = None,
    source: Optional[str] = None,
    utm_campaign: Optional[str] = None,
) -> dict:
    filters = _date_filter(date_from, date_to)
    if event_name:
        filters["event_name"] = event_name
    if product_id:
        filters["product_id"] = product_id
    if source:
        filters["source"] = source.lower()
    if utm_campaign:
        filters["utm_campaign"] = utm_campaign
    return filters


async def track_event(
    db: AsyncIOMotorDatabase,
    event_name: str,
    user_id: Optional[str] = None,
    anonymous_id: Optional[str] = None,
    session_id: Optional[str] = None,
    product_id: Optional[str] = None,
    order_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request=None,
):
    if not is_allowed_event(event_name):
        logger.info("analytics_event_rejected", extra={"event_name": event_name})
        return None

    try:
        request_data = request_metadata(request)
        metadata = metadata or {}
        source = (_clean_optional(metadata.get("source")) or derive_source(metadata, request_data["referrer"])).lower()
        utm_campaign = _clean_optional(metadata.get("utm_campaign")) or extract_utm_campaign(metadata)
        doc = {
            "event_name": event_name,
            "user_id": _clean_optional(user_id),
            "anonymous_id": _clean_optional(anonymous_id),
            "session_id": _clean_optional(session_id),
            "product_id": _clean_optional(product_id),
            "order_id": _clean_optional(order_id),
            "metadata": metadata,
            "ip_address": request_data["ip_address"],
            "user_agent": request_data["user_agent"],
            "referrer": request_data["referrer"],
            "source": source or "direct",
            "utm_campaign": utm_campaign,
            "has_account": bool(user_id),
            "created_at": datetime.utcnow(),
        }
        result = await db[ANALYTICS_EVENTS_COLLECTION].insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc
    except Exception:
        logger.exception("analytics_tracking_failed", extra={"event_name": event_name})
        return None


async def count_events(db, filters: dict, event_name: str) -> int:
    return await db[ANALYTICS_EVENTS_COLLECTION].count_documents({**filters, "event_name": event_name})


async def count_unique_visitors(db, filters: dict) -> int:
    pipeline = [
        {"$match": filters},
        {
            "$group": {
                "_id": {
                    "$ifNull": [
                        "$user_id",
                        {"$ifNull": ["$anonymous_id", {"$ifNull": ["$session_id", "$ip_address"]}]},
                    ]
                }
            }
        },
        {"$count": "count"},
    ]
    result = await db[ANALYTICS_EVENTS_COLLECTION].aggregate(pipeline).to_list(length=1)
    return int(result[0]["count"]) if result else 0


async def overview(db, filters: dict) -> dict:
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    today_filters = {"created_at": {"$gte": today_start}}
    visitors_today = await count_events(db, {**today_filters, "event_name": "page_viewed"}, "page_viewed")
    unique_visitors_today = await count_unique_visitors(db, today_filters)

    page_views = await count_events(db, filters, "page_viewed")
    product_views = await count_events(db, filters, "product_viewed")
    notify_me_clicks = await count_events(db, filters, "notify_me_clicked")
    add_to_cart = await count_events(db, filters, "add_to_cart")
    checkout_started = await count_events(db, filters, "checkout_started")
    orders_completed = await count_events(db, filters, "order_completed")
    users_with_account = await db[ANALYTICS_EVENTS_COLLECTION].count_documents({**filters, "has_account": True})

    denominator = unique_visitors_today or await count_unique_visitors(db, filters) or 1
    return {
        "visitors_today": visitors_today,
        "unique_visitors_today": unique_visitors_today,
        "page_views": page_views,
        "product_views": product_views,
        "notify_me_clicks": notify_me_clicks,
        "add_to_cart": add_to_cart,
        "checkout_started": checkout_started,
        "orders_completed": orders_completed,
        "users_with_account": users_with_account,
        "conversion_rate": round((orders_completed / denominator) * 100, 2),
        "add_to_cart_rate": round((add_to_cart / max(product_views, 1)) * 100, 2),
        "checkout_conversion_rate": round((orders_completed / max(checkout_started, 1)) * 100, 2),
    }


async def funnel(db, filters: dict) -> dict:
    names = ["product_viewed", "add_to_cart", "checkout_started", "order_completed"]
    counts = [await count_events(db, filters, name) for name in names]
    steps = []
    previous = None
    for name, count in zip(names, counts):
        conversion = None if previous is None else round((count / max(previous, 1)) * 100, 2)
        dropoff = None if previous is None else round(100 - conversion, 2)
        steps.append({
            "event_name": name,
            "count": count,
            "dropoff_from_previous": dropoff,
            "conversion_from_previous": conversion,
        })
        previous = count
    return {"steps": steps}


async def _product_names(db, product_ids: Iterable[str]) -> dict[str, str]:
    object_ids = []
    for product_id in product_ids:
        try:
            object_ids.append(ObjectId(product_id))
        except Exception:
            continue
    products = await db["products"].find({"_id": {"$in": object_ids}}, {"full_name": 1, "name": 1}).to_list(length=200)
    return {str(product["_id"]): product.get("full_name") or product.get("name") for product in products}


async def top_products(db, filters: dict, event_name: str, limit: int = 10) -> list[dict]:
    if event_name == "order_completed":
        pipeline = [
            {"$match": {**filters, "event_name": event_name}},
            {"$unwind": "$metadata.items"},
            {"$match": {"metadata.items.product_id": {"$nin": [None, ""]}}},
            {"$group": {"_id": "$metadata.items.product_id", "count": {"$sum": "$metadata.items.qty"}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
    else:
        pipeline = [
            {"$match": {**filters, "event_name": event_name, "product_id": {"$nin": [None, ""]}}},
            {"$group": {"_id": "$product_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
    rows = await db[ANALYTICS_EVENTS_COLLECTION].aggregate(pipeline).to_list(length=limit)
    names = await _product_names(db, [row["_id"] for row in rows])
    return [
        {"product_id": row["_id"], "product_name": names.get(row["_id"]), "count": row["count"]}
        for row in rows
    ]


async def product_analytics(db, filters: dict) -> dict:
    return {
        "top_products_viewed": await top_products(db, filters, "product_viewed"),
        "top_products_added_to_cart": await top_products(db, filters, "add_to_cart"),
        "top_products_purchased": await top_products(db, filters, "order_completed"),
    }


async def grouped_counts(db, filters: dict, field: str, limit: int = 20) -> list[dict]:
    pipeline = [
        {"$match": {**filters, field: {"$nin": [None, ""]}}},
        {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    rows = await db[ANALYTICS_EVENTS_COLLECTION].aggregate(pipeline).to_list(length=limit)
    return [{"label": row["_id"], "count": row["count"]} for row in rows]


async def traffic_sources(db, filters: dict) -> dict:
    return {
        "sources": await grouped_counts(db, filters, "source"),
        "campaigns": await grouped_counts(db, filters, "utm_campaign"),
    }


def _visitor_identity_expression() -> dict:
    return {
        "$ifNull": [
            "$user_id",
            {"$ifNull": ["$anonymous_id", {"$ifNull": ["$session_id", "$ip_address"]}]},
        ]
    }


def _period_expression(interval: str) -> dict:
    if interval == "minute":
        date_format = "%Y-%m-%d %H:%M"
    elif interval == "hour":
        date_format = "%Y-%m-%d %H:00"
    else:
        date_format = "%Y-%m-%d"
    return {"$dateToString": {"format": date_format, "date": "$created_at"}}


async def time_series(db, filters: dict, metric: str, interval: str = "day") -> dict:
    interval = interval if interval in {"minute", "hour"} else "day"
    period = _period_expression(interval)
    match = dict(filters)

    if metric == "visitors":
        match["event_name"] = "page_viewed"
        pipeline = [
            {"$match": match},
            {"$group": {"_id": {"period": period, "visitor": _visitor_identity_expression()}}},
            {"$group": {"_id": "$_id.period", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
    elif metric == "revenue":
        match["event_name"] = "order_completed"
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": period,
                    "count": {"$sum": 1},
                    "value": {"$sum": {"$ifNull": ["$metadata.total_amount", 0]}},
                }
            },
            {"$sort": {"_id": 1}},
        ]
    else:
        event_by_metric = {
            "page_views": "page_viewed",
            "product_views": "product_viewed",
            "add_to_cart": "add_to_cart",
            "checkout_started": "checkout_started",
            "orders_completed": "order_completed",
            "notify_me_clicks": "notify_me_clicked",
        }
        match["event_name"] = event_by_metric.get(metric, metric)
        pipeline = [
            {"$match": match},
            {"$group": {"_id": period, "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]

    rows = await db[ANALYTICS_EVENTS_COLLECTION].aggregate(pipeline).to_list(length=1000)
    return {
        "metric": metric,
        "interval": interval,
        "points": [
            {"period": row["_id"], "count": int(row.get("count", 0)), "value": row.get("value")}
            for row in rows
        ],
    }


def _device_from_user_agent(user_agent: Optional[str]) -> str:
    value = (user_agent or "").lower()
    if "ipad" in value or "tablet" in value:
        return "tablet"
    if "mobile" in value or "iphone" in value or "android" in value:
        return "mobile"
    if value:
        return "desktop"
    return "unknown"


async def device_counts(db, filters: dict) -> list[dict]:
    docs = await db[ANALYTICS_EVENTS_COLLECTION].find(filters, {"user_agent": 1}).to_list(length=10000)
    counts: dict[str, int] = {}
    for doc in docs:
        device = _device_from_user_agent(doc.get("user_agent"))
        counts[device] = counts.get(device, 0) + 1
    return [
        {"label": label, "count": count}
        for label, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


async def account_status_counts(db, filters: dict) -> list[dict]:
    total_with_account = await db[ANALYTICS_EVENTS_COLLECTION].count_documents({**filters, "has_account": True})
    total_without_account = await db[ANALYTICS_EVENTS_COLLECTION].count_documents({**filters, "has_account": False})
    return [
        {"label": "with_account", "count": total_with_account},
        {"label": "anonymous", "count": total_without_account},
    ]


async def traffic_breakdown(db, filters: dict) -> dict:
    sources = await traffic_sources(db, filters)
    return {
        "sources": sources["sources"],
        "campaigns": sources["campaigns"],
        "devices": await device_counts(db, filters),
        "account_status": await account_status_counts(db, filters),
        "events": await grouped_counts(db, filters, "event_name", limit=50),
    }


async def top_metadata_values(
    db,
    filters: dict,
    event_name: str,
    metadata_field: str,
    fallback_field: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    value_expression: Any = f"$metadata.{metadata_field}"
    if fallback_field:
        value_expression = {"$ifNull": [f"$metadata.{metadata_field}", f"$metadata.{fallback_field}"]}
    pipeline = [
        {"$match": {**filters, "event_name": event_name}},
        {"$project": {"label": value_expression, "value": "$metadata.total_amount"}},
        {"$match": {"label": {"$nin": [None, ""]}}},
        {
            "$group": {
                "_id": "$label",
                "count": {"$sum": 1},
                "value": {"$sum": {"$ifNull": ["$value", 0]}},
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    rows = await db[ANALYTICS_EVENTS_COLLECTION].aggregate(pipeline).to_list(length=limit)
    return [
        {"label": row["_id"], "count": int(row["count"]), "value": row.get("value")}
        for row in rows
    ]


async def traffic_pages(db, filters: dict, limit: int = 20) -> dict:
    return {
        "pages": await top_metadata_values(
            db,
            filters,
            "page_viewed",
            metadata_field="page_path",
            fallback_field="url",
            limit=limit,
        )
    }


async def traffic_buttons(db, filters: dict, limit: int = 20) -> dict:
    return {
        "buttons": await top_metadata_values(
            db,
            filters,
            "button_clicked",
            metadata_field="button_id",
            fallback_field="label",
            limit=limit,
        )
    }


async def traffic_dashboard(db, filters: dict, interval: str = "day") -> dict:
    return {
        "overview": await overview(db, filters),
        "funnel": await funnel(db, filters),
        "time_series": [
            await time_series(db, filters, "visitors", interval),
            await time_series(db, filters, "page_views", interval),
            await time_series(db, filters, "product_views", interval),
            await time_series(db, filters, "add_to_cart", interval),
            await time_series(db, filters, "checkout_started", interval),
            await time_series(db, filters, "orders_completed", interval),
            await time_series(db, filters, "revenue", interval),
        ],
        "breakdown": await traffic_breakdown(db, filters),
        "pages": await traffic_pages(db, filters),
        "buttons": await traffic_buttons(db, filters),
        "products": await product_analytics(db, filters),
        "recent_events": await recent_events(db, filters, limit=25),
    }


async def count_all(db, filters: dict) -> int:
    return await db[ANALYTICS_EVENTS_COLLECTION].count_documents(filters)


def event_to_read(doc: dict) -> dict:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    return payload


async def recent_events(db, filters: dict, limit: int = 50) -> list[dict]:
    docs = await (
        db[ANALYTICS_EVENTS_COLLECTION]
        .find(filters)
        .sort("created_at", DESCENDING)
        .limit(limit)
        .to_list(length=limit)
    )
    return [event_to_read(doc) for doc in docs]


async def event_page(db, filters: dict, page: int = 1, page_size: int = 50) -> dict:
    page = max(page, 1)
    page_size = max(1, min(page_size, 500))
    total = await count_all(db, filters)
    skip = (page - 1) * page_size
    docs = await (
        db[ANALYTICS_EVENTS_COLLECTION]
        .find(filters)
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(page_size)
        .to_list(length=page_size)
    )
    return {
        "items": [event_to_read(doc) for doc in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


async def traffic_all_data(
    db,
    filters: dict,
    interval: str = "day",
    page: int = 1,
    page_size: int = 100,
) -> dict:
    dashboard = await traffic_dashboard(db, filters, interval=interval)
    dashboard["events"] = await event_page(db, filters, page=page, page_size=page_size)
    return dashboard


async def traffic_realtime(db, filters: dict, window_minutes: int = 1) -> dict:
    window_minutes = max(1, min(window_minutes, 1440))
    realtime_filters = {
        **filters,
        "created_at": {
            **filters.get("created_at", {}),
            "$gte": datetime.utcnow() - timedelta(minutes=window_minutes),
        },
    }
    return {
        "window_minutes": window_minutes,
        "overview": await overview(db, realtime_filters),
        "funnel": await funnel(db, realtime_filters),
        "time_series": [
            await time_series(db, realtime_filters, "visitors", "minute"),
            await time_series(db, realtime_filters, "page_views", "minute"),
            await time_series(db, realtime_filters, "product_views", "minute"),
            await time_series(db, realtime_filters, "add_to_cart", "minute"),
            await time_series(db, realtime_filters, "checkout_started", "minute"),
            await time_series(db, realtime_filters, "orders_completed", "minute"),
            await time_series(db, realtime_filters, "revenue", "minute"),
        ],
        "breakdown": await traffic_breakdown(db, realtime_filters),
        "recent_events": await recent_events(db, realtime_filters, limit=100),
    }
