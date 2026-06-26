from datetime import datetime, timedelta

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.domain.order_constants import OUTBOX_FAILED, OUTBOX_PENDING, OUTBOX_PROCESSING, OUTBOX_SENT


COLLECTION = "outbox_events"


def parse_object_id(value: str) -> ObjectId:
    return ObjectId(value)


async def enqueue(
    db,
    session=None,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    operation_key: str,
    payload: dict,
    provider: str | None = None,
    event_name: str | None = None,
    event_id: str | None = None,
    payload_json: dict | None = None,
) -> bool:
    doc = {
        "event_type": event_type,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "operation_key": operation_key,
        "provider": provider,
        "event_name": event_name,
        "event_id": event_id,
        "payload": payload,
        "payload_json": payload_json or payload,
        "status": OUTBOX_PENDING,
        "attempts": 0,
        "next_retry_at": None,
        "last_error": None,
        "created_at": datetime.utcnow(),
        "processed_at": None,
        "sent_at": None,
    }
    try:
        await db[COLLECTION].insert_one(doc, session=session)
        return True
    except DuplicateKeyError:
        return False


async def claim_event(db, *, operation_key: str, provider: str | None = None) -> dict | None:
    query = {"operation_key": operation_key, "status": {"$in": [OUTBOX_PENDING, OUTBOX_FAILED]}}
    if provider:
        query["provider"] = provider
    return await db[COLLECTION].find_one_and_update(
        query,
        {"$set": {"status": OUTBOX_PROCESSING, "processed_at": datetime.utcnow()}},
    )


async def claim_next_due_event(db, *, provider: str) -> dict | None:
    now = datetime.utcnow()
    query = {
        "provider": provider,
        "$or": [
            {"status": OUTBOX_PENDING},
            {"status": OUTBOX_FAILED, "next_retry_at": {"$lte": now}},
        ],
    }
    return await db[COLLECTION].find_one_and_update(
        query,
        {"$set": {"status": OUTBOX_PROCESSING, "processed_at": now}},
        sort=[("created_at", 1)],
    )


async def mark_sent(db, outbox_id: ObjectId) -> None:
    now = datetime.utcnow()
    await db[COLLECTION].update_one(
        {"_id": outbox_id},
        {"$set": {"status": OUTBOX_SENT, "sent_at": now, "processed_at": now, "next_retry_at": None, "last_error": None}},
    )


async def mark_failed(db, outbox_id: ObjectId, *, last_error: str, retryable: bool) -> None:
    existing = await db[COLLECTION].find_one({"_id": outbox_id}, {"attempts": 1})
    attempts = int((existing or {}).get("attempts", 0)) + 1
    next_retry_at = datetime.utcnow() + timedelta(minutes=min(attempts * 5, 60)) if retryable else None
    await db[COLLECTION].update_one(
        {"_id": outbox_id},
        {
            "$set": {
                "status": OUTBOX_FAILED,
                "attempts": attempts,
                "next_retry_at": next_retry_at,
                "last_error": last_error[:300],
            }
        },
    )
