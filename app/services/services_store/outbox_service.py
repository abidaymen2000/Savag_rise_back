from datetime import datetime, timedelta

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.domain.order_constants import OUTBOX_DEAD_LETTER, OUTBOX_FAILED, OUTBOX_PENDING, OUTBOX_PROCESSING, OUTBOX_SENT


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
    max_attempts: int | None = None,
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
        "max_attempts": int(max_attempts or settings.META_OUTBOX_MAX_ATTEMPTS),
        "locked_at": None,
        "locked_by": None,
        "next_retry_at": None,
        "last_error": None,
        "created_at": datetime.utcnow(),
        "last_attempted_at": None,
        "processed_at": None,
        "sent_at": None,
    }
    try:
        await db[COLLECTION].insert_one(doc, session=session)
        return True
    except DuplicateKeyError:
        return False


def _claim_query(*, provider: str | None = None, operation_key: str | None = None, now: datetime | None = None) -> dict:
    claim_now = now or datetime.utcnow()
    stale_cutoff = claim_now - timedelta(seconds=settings.META_OUTBOX_LOCK_TIMEOUT_SECONDS)
    base_status_query = [
        {"status": OUTBOX_PENDING},
        {"status": OUTBOX_FAILED, "next_retry_at": {"$lte": claim_now}},
        {"status": OUTBOX_PROCESSING, "locked_at": {"$lte": stale_cutoff}},
    ]
    query: dict = {"$or": base_status_query}
    if provider:
        query["provider"] = provider
    if operation_key:
        query["operation_key"] = operation_key
    return query


async def claim_event(db, *, operation_key: str, provider: str | None = None, worker_id: str) -> dict | None:
    now = datetime.utcnow()
    query = _claim_query(provider=provider, operation_key=operation_key, now=now)
    return await db[COLLECTION].find_one_and_update(
        query,
        {
            "$set": {
                "status": OUTBOX_PROCESSING,
                "processed_at": now,
                "locked_at": now,
                "locked_by": worker_id,
                "last_attempted_at": now,
                "last_error": None,
            },
            "$inc": {"attempts": 1},
        },
        return_document=ReturnDocument.AFTER,
    )


async def claim_next_due_event(db, *, provider: str, worker_id: str) -> dict | None:
    now = datetime.utcnow()
    query = _claim_query(provider=provider, now=now)
    return await db[COLLECTION].find_one_and_update(
        query,
        {
            "$set": {
                "status": OUTBOX_PROCESSING,
                "processed_at": now,
                "locked_at": now,
                "locked_by": worker_id,
                "last_attempted_at": now,
                "last_error": None,
            },
            "$inc": {"attempts": 1},
        },
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


async def mark_sent(db, outbox_id: ObjectId) -> None:
    now = datetime.utcnow()
    await db[COLLECTION].update_one(
        {"_id": outbox_id},
        {
            "$set": {
                "status": OUTBOX_SENT,
                "sent_at": now,
                "processed_at": now,
                "next_retry_at": None,
                "last_error": None,
                "locked_at": None,
                "locked_by": None,
            }
        },
    )


def compute_backoff_seconds(attempts: int, *, retry_after_seconds: int | None = None) -> int:
    if retry_after_seconds is not None:
        return min(max(retry_after_seconds, 1), settings.META_OUTBOX_MAX_BACKOFF_SECONDS)
    base_delay = min(2 ** max(attempts - 1, 0), settings.META_OUTBOX_MAX_BACKOFF_SECONDS)
    return max(base_delay, 1)


async def mark_failed(
    db,
    outbox_id: ObjectId,
    *,
    last_error: str,
    retryable: bool,
    retry_after_seconds: int | None = None,
) -> None:
    existing = await db[COLLECTION].find_one({"_id": outbox_id}, {"attempts": 1, "max_attempts": 1})
    attempts = int((existing or {}).get("attempts", 0))
    max_attempts = int((existing or {}).get("max_attempts", settings.META_OUTBOX_MAX_ATTEMPTS))
    exhausted = attempts >= max_attempts
    next_retry_at = None
    next_status = OUTBOX_DEAD_LETTER if (not retryable or exhausted) else OUTBOX_FAILED
    if next_status == OUTBOX_FAILED:
        next_retry_at = datetime.utcnow() + timedelta(seconds=compute_backoff_seconds(attempts, retry_after_seconds=retry_after_seconds))
    await db[COLLECTION].update_one(
        {"_id": outbox_id},
        {
            "$set": {
                "status": next_status,
                "next_retry_at": next_retry_at,
                "last_error": last_error[:300],
                "locked_at": None,
                "locked_by": None,
            }
        },
    )
