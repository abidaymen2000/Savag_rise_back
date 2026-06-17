from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.drop_countdown import DropCountdownOut, DropCountdownUpdate

router = APIRouter(tags=["drop-countdown"])

SETTINGS_COLLECTION = "cms_settings"
DROP_COUNTDOWN_KEY = "store_drop_countdown"


async def _get_drop_doc(db) -> Optional[dict]:
    return await db[SETTINGS_COLLECTION].find_one({"_id": DROP_COUNTDOWN_KEY})


def _seconds_remaining(launch_at: datetime) -> int:
    return max(0, int((launch_at - datetime.utcnow()).total_seconds()))


def _doc_to_out(doc: dict) -> DropCountdownOut:
    value = doc["value"]
    launch_at = value["launch_at"]
    return DropCountdownOut(
        **value,
        seconds_remaining=_seconds_remaining(launch_at),
        is_released=datetime.utcnow() >= launch_at,
        notification_sent_at=doc.get("notification_sent_at"),
        notification_recipients_count=doc.get("notification_recipients_count", 0),
    )


@router.get("/storefront/drop-countdown", response_model=DropCountdownOut)
async def read_storefront_drop_countdown(db=Depends(get_db)):
    doc = await _get_drop_doc(db)
    if not doc or not doc.get("value", {}).get("is_active", False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop actif configure")
    return _doc_to_out(doc)


@router.get("/admin/drop-countdown", response_model=DropCountdownOut)
async def admin_get_drop_countdown(
    _admin=Depends(require_permission("drop_countdown")),
    db=Depends(get_db),
):
    doc = await _get_drop_doc(db)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun drop configure")
    return _doc_to_out(doc)


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
    return _doc_to_out(updated)
