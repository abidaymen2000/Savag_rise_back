from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_db
from app.dependencies import get_current_user
from app.dependencies_admin import require_permission
from app.schemas.drop_countdown import DropCountdownOut, DropCountdownUpdate, DropNotificationStatus

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
