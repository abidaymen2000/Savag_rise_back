from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from bson import ObjectId

from app.db import get_db
from app.dependencies import get_current_user
from app.dependencies_admin import require_permission
from app.schemas.drop_countdown import (
    DropCountdownOut,
    DropCountdownUpdate,
    DropNotificationStatus,
    DropSubscriberOut,
    DropSubscribersPage,
)

router = APIRouter(tags=["drop-countdown"])

SETTINGS_COLLECTION = "cms_settings"
DROP_COUNTDOWN_KEY = "store_drop_countdown"
SUBSCRIBERS_COLLECTION = "drop_notification_subscribers"


async def _get_drop_doc(db) -> Optional[dict]:
    return await db[SETTINGS_COLLECTION].find_one({"_id": DROP_COUNTDOWN_KEY})


def _seconds_remaining(launch_at: datetime) -> int:
    return max(0, int((launch_at - datetime.utcnow()).total_seconds()))


def drop_key_from_value(value: dict) -> str:
    launch_at = value["launch_at"]
    if isinstance(launch_at, datetime):
        launch_part = launch_at.isoformat()
    else:
        launch_part = str(launch_at)
    return f"{value.get('drop_name', 'drop')}::{launch_part}"


async def _subscribers_count(db, value: dict) -> int:
    return await db[SUBSCRIBERS_COLLECTION].count_documents({
        "drop_key": drop_key_from_value(value),
    })


def _subscriber_out(subscription: dict, user: Optional[dict]) -> DropSubscriberOut:
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


async def _doc_to_out(db, doc: dict) -> DropCountdownOut:
    value = doc["value"]
    launch_at = value["launch_at"]
    return DropCountdownOut(
        **value,
        seconds_remaining=_seconds_remaining(launch_at),
        is_released=datetime.utcnow() >= launch_at,
        notification_sent_at=doc.get("notification_sent_at"),
        notification_recipients_count=doc.get("notification_recipients_count", 0),
        subscribers_count=await _subscribers_count(db, value),
    )


@router.get("/storefront/drop-countdown", response_model=DropCountdownOut)
async def read_storefront_drop_countdown(db=Depends(get_db)):
    doc = await _get_drop_doc(db)
    if not doc or not doc.get("value", {}).get("is_active", False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop actif configure")
    return await _doc_to_out(db, doc)


@router.get("/storefront/drop-countdown/notification-status", response_model=DropNotificationStatus)
async def read_drop_notification_status(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    doc = await _get_drop_doc(db)
    if not doc or not doc.get("value", {}).get("is_active", False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop actif configure")

    drop_key = drop_key_from_value(doc["value"])
    user_id = str(current_user["_id"])
    subscription = await db[SUBSCRIBERS_COLLECTION].find_one({
        "drop_key": drop_key,
        "user_id": user_id,
    })
    return DropNotificationStatus(
        drop_key=drop_key,
        is_subscribed=subscription is not None,
        subscribers_count=await _subscribers_count(db, doc["value"]),
    )


@router.post("/storefront/drop-countdown/notify-me", response_model=DropNotificationStatus, status_code=201)
async def subscribe_drop_notification(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    doc = await _get_drop_doc(db)
    if not doc or not doc.get("value", {}).get("is_active", False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop actif configure")
    if not doc["value"].get("email_enabled", True):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Les notifications de ce drop sont desactivees")
    if datetime.utcnow() >= doc["value"]["launch_at"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le drop est deja sorti")

    drop_key = drop_key_from_value(doc["value"])
    user_id = str(current_user["_id"])
    await db[SUBSCRIBERS_COLLECTION].update_one(
        {"drop_key": drop_key, "user_id": user_id},
        {
            "$set": {
                "email": current_user["email"],
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {
                "drop_key": drop_key,
                "user_id": user_id,
                "created_at": datetime.utcnow(),
            },
        },
        upsert=True,
    )
    return DropNotificationStatus(
        drop_key=drop_key,
        is_subscribed=True,
        subscribers_count=await _subscribers_count(db, doc["value"]),
    )


@router.delete("/storefront/drop-countdown/notify-me", response_model=DropNotificationStatus)
async def unsubscribe_drop_notification(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    doc = await _get_drop_doc(db)
    if not doc or not doc.get("value", {}).get("is_active", False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop actif configure")

    drop_key = drop_key_from_value(doc["value"])
    await db[SUBSCRIBERS_COLLECTION].delete_one({
        "drop_key": drop_key,
        "user_id": str(current_user["_id"]),
    })
    return DropNotificationStatus(
        drop_key=drop_key,
        is_subscribed=False,
        subscribers_count=await _subscribers_count(db, doc["value"]),
    )


@router.get("/admin/drop-countdown", response_model=DropCountdownOut)
async def admin_get_drop_countdown(
    _admin=Depends(require_permission("drop_countdown")),
    db=Depends(get_db),
):
    doc = await _get_drop_doc(db)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop configure")
    return await _doc_to_out(db, doc)


@router.get("/admin/drop-countdown/subscribers", response_model=DropSubscribersPage)
async def admin_list_drop_subscribers(
    _admin=Depends(require_permission("drop_countdown")),
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: Optional[str] = Query(None, description="Recherche email ou nom"),
    current_drop_only: bool = Query(True),
):
    filters = {}
    drop_key = None

    if current_drop_only:
        doc = await _get_drop_doc(db)
        if not doc:
            return DropSubscribersPage(items=[], total=0, page=page, page_size=page_size, pages=0)
        drop_key = drop_key_from_value(doc["value"])
        filters["drop_key"] = drop_key

    user_filters = {}
    if q:
        user_filters["$or"] = [
            {"email": {"$regex": q, "$options": "i"}},
            {"full_name": {"$regex": q, "$options": "i"}},
        ]
        matching_users = await db["users"].find(user_filters, {"_id": 1}).to_list(length=5000)
        matching_user_ids = [str(user["_id"]) for user in matching_users]
        filters["$or"] = [
            {"email": {"$regex": q, "$options": "i"}},
            {"user_id": {"$in": matching_user_ids}},
        ]

    skip = (page - 1) * page_size
    total = await db[SUBSCRIBERS_COLLECTION].count_documents(filters)
    subscriptions = await (
        db[SUBSCRIBERS_COLLECTION]
        .find(filters)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
        .to_list(length=page_size)
    )

    user_ids = []
    for subscription in subscriptions:
        try:
            user_ids.append(ObjectId(subscription["user_id"]))
        except Exception:
            continue

    users = await db["users"].find({"_id": {"$in": user_ids}}).to_list(length=len(user_ids))
    users_by_id = {str(user["_id"]): user for user in users}
    items = [
        _subscriber_out(subscription, users_by_id.get(subscription["user_id"]))
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


@router.put("/admin/drop-countdown", response_model=DropCountdownOut)
async def admin_update_drop_countdown(
    payload: DropCountdownUpdate,
    _admin=Depends(require_permission("drop_countdown")),
    db=Depends(get_db),
):
    value = payload.model_dump()
    existing = await _get_drop_doc(db)
    reset_notification = True

    if existing and existing.get("value"):
        previous = existing["value"]
        reset_notification = (
            previous.get("launch_at") != value["launch_at"]
            or previous.get("drop_name") != value["drop_name"]
            or previous.get("email_subject") != value["email_subject"]
        )

    update = {
        "$set": {
            "value": value,
            "updated_at": datetime.utcnow(),
        },
        "$setOnInsert": {"created_at": datetime.utcnow()},
    }
    if reset_notification:
        update["$unset"] = {
            "notification_sent_at": "",
            "notification_claimed_at": "",
            "notification_status": "",
            "notification_recipients_count": "",
            "notification_failures_count": "",
        }

    await db[SETTINGS_COLLECTION].update_one(
        {"_id": DROP_COUNTDOWN_KEY},
        update,
        upsert=True,
    )
    updated = await _get_drop_doc(db)
    return await _doc_to_out(db, updated)
