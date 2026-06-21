from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, Request, status

from app.analytics.service import track_event
from app.crud import drop_countdown as countdown_crud
from app.schemas.drop_countdown import (
    DropCountdownOut,
    DropNotificationStatus,
    DropSubscriberOut,
    DropSubscribersPage,
)


def seconds_remaining(launch_at: datetime) -> int:
    return max(0, int((launch_at - datetime.utcnow()).total_seconds()))


def drop_key_from_value(value: dict) -> str:
    launch_at = value["launch_at"]
    launch_part = launch_at.isoformat() if isinstance(launch_at, datetime) else str(launch_at)
    return f"{value.get('drop_name', 'drop')}::{launch_part}"


async def subscribers_count(db, value: dict) -> int:
    return await countdown_crud.count_subscribers(db, {"drop_key": drop_key_from_value(value)})


def subscriber_out(subscription: dict, user: Optional[dict]) -> DropSubscriberOut:
    return DropSubscriberOut(
        id=str(subscription["_id"]),
        drop_key=subscription["drop_key"],
        user_id=subscription["user_id"],
        email=(user or {}).get("email") or subscription.get("email") or "",
        full_name=(user or {}).get("full_name"),
        user_is_active=(user or {}).get("is_active", False),
        user_created_at=(user or {}).get("created_at"),
        subscribed_at=subscription.get("created_at") or subscription.get("updated_at"),
        updated_at=subscription.get("updated_at"),
    )


async def doc_to_out(db, doc: dict) -> DropCountdownOut:
    value = doc["value"]
    launch_at = value["launch_at"]
    return DropCountdownOut(
        **value,
        seconds_remaining=seconds_remaining(launch_at),
        is_released=datetime.utcnow() >= launch_at,
        notification_sent_at=doc.get("notification_sent_at"),
        notification_recipients_count=doc.get("notification_recipients_count", 0),
        subscribers_count=await subscribers_count(db, value),
    )


async def get_active_storefront_drop(db) -> DropCountdownOut:
    doc = await countdown_crud.find_drop_doc(db)
    if not doc or not doc.get("value", {}).get("is_active", False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop actif configure")
    return await doc_to_out(db, doc)


async def get_admin_drop(db) -> DropCountdownOut:
    doc = await countdown_crud.find_drop_doc(db)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop configure")
    return await doc_to_out(db, doc)


async def get_notification_status(db, current_user) -> DropNotificationStatus:
    doc = await countdown_crud.find_drop_doc(db)
    if not doc or not doc.get("value", {}).get("is_active", False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop actif configure")

    drop_key = drop_key_from_value(doc["value"])
    user_id = str(current_user["_id"])
    subscription = await countdown_crud.find_subscription(db, drop_key, user_id)
    return DropNotificationStatus(
        drop_key=drop_key,
        is_subscribed=subscription is not None,
        subscribers_count=await subscribers_count(db, doc["value"]),
    )


async def subscribe_notification(db, request: Request, current_user) -> DropNotificationStatus:
    doc = await countdown_crud.find_drop_doc(db)
    if not doc or not doc.get("value", {}).get("is_active", False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop actif configure")
    if not doc["value"].get("email_enabled", True):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Les notifications de ce drop sont desactivees")
    if datetime.utcnow() >= doc["value"]["launch_at"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le drop est deja sorti")

    drop_key = drop_key_from_value(doc["value"])
    user_id = str(current_user["_id"])
    await countdown_crud.upsert_subscription(db, drop_key, user_id, current_user["email"], datetime.utcnow())
    await track_event(
        db,
        "notify_me_clicked",
        user_id=user_id,
        metadata={
            "drop_key": drop_key,
            "drop_name": doc["value"].get("drop_name"),
            "drop_date": doc["value"].get("launch_at").isoformat() if doc["value"].get("launch_at") else None,
        },
        request=request,
    )
    return DropNotificationStatus(
        drop_key=drop_key,
        is_subscribed=True,
        subscribers_count=await subscribers_count(db, doc["value"]),
    )


async def unsubscribe_notification(db, current_user) -> DropNotificationStatus:
    doc = await countdown_crud.find_drop_doc(db)
    if not doc or not doc.get("value", {}).get("is_active", False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop actif configure")

    drop_key = drop_key_from_value(doc["value"])
    await countdown_crud.delete_subscription(db, drop_key, str(current_user["_id"]))
    return DropNotificationStatus(
        drop_key=drop_key,
        is_subscribed=False,
        subscribers_count=await subscribers_count(db, doc["value"]),
    )


async def list_subscribers(db, page: int, page_size: int, q: Optional[str], current_drop_only: bool) -> DropSubscribersPage:
    filters = {}
    drop_key = None

    if current_drop_only:
        doc = await countdown_crud.find_drop_doc(db)
        if not doc:
            return DropSubscribersPage(items=[], total=0, page=page, page_size=page_size, pages=0)
        drop_key = drop_key_from_value(doc["value"])
        filters["drop_key"] = drop_key

    if q:
        user_filters = {
            "$or": [
                {"email": {"$regex": q, "$options": "i"}},
                {"full_name": {"$regex": q, "$options": "i"}},
            ]
        }
        matching_users = await countdown_crud.list_matching_user_ids(db, user_filters, limit=5000)
        matching_user_ids = [str(user["_id"]) for user in matching_users]
        filters["$or"] = [
            {"email": {"$regex": q, "$options": "i"}},
            {"user_id": {"$in": matching_user_ids}},
        ]

    skip = (page - 1) * page_size
    total = await countdown_crud.count_subscribers(db, filters)
    subscriptions = await countdown_crud.list_subscribers(db, filters, skip, page_size)

    user_ids = []
    for subscription in subscriptions:
        try:
            user_ids.append(ObjectId(subscription["user_id"]))
        except Exception:
            continue

    users = await countdown_crud.list_users_by_ids(db, user_ids)
    users_by_id = {str(user["_id"]): user for user in users}
    items = [
        subscriber_out(subscription, users_by_id.get(subscription["user_id"]))
        for subscription in subscriptions
    ]

    return DropSubscribersPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
        drop_key=drop_key,
    )


async def update_drop_countdown(db, payload) -> DropCountdownOut:
    value = payload.model_dump()
    existing = await countdown_crud.find_drop_doc(db)
    reset_notification = True

    if existing and existing.get("value"):
        previous = existing["value"]
        reset_notification = (
            previous.get("launch_at") != value["launch_at"]
            or previous.get("drop_name") != value["drop_name"]
            or previous.get("email_subject") != value["email_subject"]
        )

    now = datetime.utcnow()
    update = {
        "$set": {
            "value": value,
            "updated_at": now,
        },
        "$setOnInsert": {"created_at": now},
    }
    if reset_notification:
        update["$unset"] = {
            "notification_sent_at": "",
            "notification_claimed_at": "",
            "notification_status": "",
            "notification_recipients_count": "",
            "notification_failures_count": "",
        }

    await countdown_crud.save_drop_countdown(db, update)
    updated = await countdown_crud.find_drop_doc(db)
    return await doc_to_out(db, updated)
