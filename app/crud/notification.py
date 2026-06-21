from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId


COLLECTION = "admin_notifications"


def visibility_filter(admin_id: str) -> Dict[str, Any]:
    return {
        "$or": [
            {"recipient_admin_id": None},
            {"recipient_admin_id": {"$exists": False}},
            {"recipient_admin_id": admin_id},
        ]
    }


async def insert_notification(db, data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    doc = {
        **data,
        "created_at": now,
        "read_by_admin_ids": [],
        "read_at_by_admin_ids": {},
    }
    res = await db[COLLECTION].insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def list_notifications(
    db,
    *,
    admin_id: str,
    filters: Dict[str, Any],
    skip: int,
    limit: int,
) -> List[Dict[str, Any]]:
    query = {"$and": [visibility_filter(admin_id), filters or {}]}
    return await (
        db[COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )


async def count_notifications(db, *, admin_id: str, filters: Dict[str, Any]) -> int:
    query = {"$and": [visibility_filter(admin_id), filters or {}]}
    return await db[COLLECTION].count_documents(query)


async def find_notification(db, notification_id: str) -> Optional[Dict[str, Any]]:
    try:
        oid = ObjectId(notification_id)
    except Exception:
        return None
    return await db[COLLECTION].find_one({"_id": oid})


async def mark_notification_read(db, *, notification_id: str, admin_id: str) -> Optional[Dict[str, Any]]:
    try:
        oid = ObjectId(notification_id)
    except Exception:
        return None
    now = datetime.utcnow()
    await db[COLLECTION].update_one(
        {"_id": oid, **visibility_filter(admin_id)},
        {
            "$addToSet": {"read_by_admin_ids": admin_id},
            "$set": {f"read_at_by_admin_ids.{admin_id}": now},
        },
    )
    return await db[COLLECTION].find_one({"_id": oid})


async def mark_all_notifications_read(db, *, admin_id: str) -> int:
    now = datetime.utcnow()
    res = await db[COLLECTION].update_many(
        {
            **visibility_filter(admin_id),
            "read_by_admin_ids": {"$ne": admin_id},
        },
        {
            "$addToSet": {"read_by_admin_ids": admin_id},
            "$set": {f"read_at_by_admin_ids.{admin_id}": now},
        },
    )
    return int(res.modified_count)
