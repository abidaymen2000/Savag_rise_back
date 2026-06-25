from datetime import datetime
from pymongo.errors import DuplicateKeyError

from app.domain.order_constants import OUTBOX_PENDING


COLLECTION = "outbox_events"


async def enqueue(
    db,
    session=None,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    operation_key: str,
    payload: dict,
) -> bool:
    doc = {
        "event_type": event_type,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "operation_key": operation_key,
        "payload": payload,
        "status": OUTBOX_PENDING,
        "attempts": 0,
        "next_retry_at": None,
        "last_error": None,
        "created_at": datetime.utcnow(),
        "processed_at": None,
    }
    try:
        await db[COLLECTION].insert_one(doc, session=session)
        return True
    except DuplicateKeyError:
        return False
