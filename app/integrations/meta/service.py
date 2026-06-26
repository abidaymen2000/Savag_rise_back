import asyncio
import logging
import os
import socket
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import Request

from app.analytics.utils import get_client_ip
from app.config import settings
from app.integrations.meta.client import (
    MetaConversionsApiClient,
    MetaDisabledError,
    MetaPermanentError,
    MetaRetryableError,
)
from app.integrations.meta.hashing import (
    normalize_city,
    normalize_country,
    normalize_email,
    normalize_external_id,
    normalize_name,
    normalize_phone,
    normalized_sha256,
)
from app.integrations.meta.schemas import MetaEventContext, MetaEventData, MetaEventsRequest
from app.services.services_store import outbox_service


logger = logging.getLogger("meta.service")
META_PROVIDER = "meta"


def is_meta_enabled() -> bool:
    return bool(
        settings.META_CAPI_ENABLED
        and settings.META_PIXEL_ID
        and settings.META_CONVERSIONS_API_TOKEN is not None
    )


def _split_full_name(full_name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not full_name:
        return None, None
    parts = [part for part in str(full_name).strip().split(" ") if part]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def _append_if_present(target: dict, key: str, value: Optional[str]) -> None:
    if value:
        target.setdefault(key, []).append(value)


def _decimal_to_number(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_meta_worker_id(prefix: str = "meta-worker") -> str:
    dyno = os.getenv("DYNO", "local")
    return f"{prefix}:{dyno}:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def build_meta_context(request: Optional[Request], incoming: Optional[dict] = None) -> MetaEventContext:
    if incoming and hasattr(incoming, "model_dump"):
        payload = incoming.model_dump(exclude_none=True)
    else:
        payload = incoming or {}
    return MetaEventContext(
        event_id=payload.get("event_id"),
        event_source_url=payload.get("event_source_url") or (str(request.url) if request else None),
        fbp=payload.get("fbp") or (request.cookies.get("_fbp") if request else None),
        fbc=payload.get("fbc") or (request.cookies.get("_fbc") if request else None),
        fbclid=payload.get("fbclid") or (request.query_params.get("fbclid") if request else None),
        client_ip_address=get_client_ip(request),
        client_user_agent=request.headers.get("user-agent") if request else None,
    )


def persisted_meta_context(context: MetaEventContext) -> dict[str, str]:
    payload = {
        "event_source_url": context.event_source_url,
        "fbp": context.fbp,
        "fbc": context.fbc,
        "fbclid": context.fbclid,
    }
    return {key: value for key, value in payload.items() if value}


def _merged_meta_context(stored: dict | None, override: MetaEventContext | None) -> MetaEventContext:
    base = MetaEventContext.model_validate(stored or {})
    if not override:
        return base
    merged = base.model_dump(exclude_none=True)
    merged.update(override.model_dump(exclude_none=True))
    return MetaEventContext.model_validate(merged)


def _build_user_data(
    *,
    email: Optional[str],
    phone: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    city: Optional[str],
    country: Optional[str],
    external_id: Optional[str],
    context: MetaEventContext,
) -> dict:
    user_data: dict[str, object] = {}
    _append_if_present(user_data, "em", normalized_sha256(email, normalizer=normalize_email))
    _append_if_present(user_data, "ph", normalized_sha256(phone, normalizer=normalize_phone))
    _append_if_present(user_data, "fn", normalized_sha256(first_name, normalizer=normalize_name))
    _append_if_present(user_data, "ln", normalized_sha256(last_name, normalizer=normalize_name))
    _append_if_present(user_data, "ct", normalized_sha256(city, normalizer=normalize_city))
    _append_if_present(user_data, "country", normalized_sha256(country, normalizer=normalize_country))
    _append_if_present(user_data, "external_id", normalized_sha256(external_id, normalizer=normalize_external_id))
    if context.client_ip_address:
        user_data["client_ip_address"] = context.client_ip_address
    if context.client_user_agent:
        user_data["client_user_agent"] = context.client_user_agent
    if context.fbp:
        user_data["fbp"] = context.fbp
    fbc = context.fbc
    if not fbc and context.fbclid:
        fbc = f"fb.1.{int(datetime.utcnow().timestamp())}.{context.fbclid}"
    if fbc:
        user_data["fbc"] = fbc
    return user_data


def build_purchase_payload(order: dict, *, meta_context: MetaEventContext | None = None) -> dict:
    order_id = str(order["_id"])
    shipping = order.get("shipping") or {}
    first_name, last_name = _split_full_name(shipping.get("full_name"))
    context = _merged_meta_context(order.get("meta_context"), meta_context)
    user_data = _build_user_data(
        email=shipping.get("email") or order.get("user_email"),
        phone=shipping.get("phone"),
        first_name=first_name,
        last_name=last_name,
        city=shipping.get("city"),
        country=shipping.get("country"),
        external_id=order.get("user_id"),
        context=context,
    )
    contents = []
    content_ids: list[str] = []
    num_items = 0
    for line in order.get("item_snapshots", []):
        item_id = line.get("meta_content_id") or line.get("variant_id")
        qty = int(line.get("qty", 0) or 0)
        unit_price = Decimal(str(line.get("unit_price_final", line.get("unit_price", 0)) or 0))
        contents.append({"id": item_id, "quantity": qty, "item_price": _decimal_to_number(unit_price)})
        content_ids.append(item_id)
        num_items += qty
    event = MetaEventData(
        event_name="Purchase",
        event_time=int((order.get("created_at") or datetime.utcnow()).timestamp()),
        event_id=f"purchase:{order_id}",
        event_source_url=context.event_source_url,
        user_data=user_data,
        custom_data={
            "currency": "TND",
            "value": _decimal_to_number(Decimal(str(order.get("total_amount", 0) or 0))),
            "order_id": order_id,
            "content_type": "product",
            "content_ids": content_ids,
            "contents": contents,
            "num_items": num_items,
        },
    )
    payload = MetaEventsRequest(data=[event])
    if settings.META_TEST_EVENT_CODE:
        payload.test_event_code = settings.META_TEST_EVENT_CODE
    return payload.model_dump(exclude_none=True)


def build_complete_registration_payload(user: dict, *, meta_context: MetaEventContext | None = None) -> dict:
    first_name, last_name = _split_full_name(user.get("full_name"))
    context = _merged_meta_context(user.get("meta_context"), meta_context)
    user_data = _build_user_data(
        email=user.get("email"),
        phone=user.get("phone"),
        first_name=first_name,
        last_name=last_name,
        city=user.get("city"),
        country=user.get("country"),
        external_id=str(user["_id"]),
        context=context,
    )
    event = MetaEventData(
        event_name="CompleteRegistration",
        event_time=int((user.get("created_at") or datetime.utcnow()).timestamp()),
        event_id=f"registration:{user['_id']}",
        event_source_url=context.event_source_url,
        user_data=user_data,
        custom_data={},
    )
    payload = MetaEventsRequest(data=[event])
    if settings.META_TEST_EVENT_CODE:
        payload.test_event_code = settings.META_TEST_EVENT_CODE
    return payload.model_dump(exclude_none=True)


async def enqueue_purchase_event(db, order: dict, *, session=None, meta_context: MetaEventContext | None = None) -> bool:
    if not is_meta_enabled():
        return False
    order_id = str(order["_id"])
    payload = build_purchase_payload(order, meta_context=meta_context)
    return await outbox_service.enqueue(
        db,
        session=session,
        event_type="meta_purchase_pending",
        aggregate_type="order",
        aggregate_id=order_id,
        operation_key=f"meta:purchase:{order_id}",
        payload={"order_id": order_id},
        provider=META_PROVIDER,
        event_name="Purchase",
        event_id=f"purchase:{order_id}",
        payload_json=payload,
    )


async def enqueue_complete_registration_event(db, user: dict, *, meta_context: MetaEventContext | None = None) -> bool:
    if not is_meta_enabled():
        return False
    user_id = str(user["_id"])
    payload = build_complete_registration_payload(user, meta_context=meta_context)
    return await outbox_service.enqueue(
        db,
        event_type="meta_complete_registration_pending",
        aggregate_type="user",
        aggregate_id=user_id,
        operation_key=f"meta:registration:{user_id}",
        payload={"user_id": user_id},
        provider=META_PROVIDER,
        event_name="CompleteRegistration",
        event_id=f"registration:{user_id}",
        payload_json=payload,
    )


async def _send_meta_event_for_outbox(db, outbox_doc: dict) -> dict:
    payload = outbox_doc.get("payload_json")
    if not payload:
        raise MetaPermanentError("Meta payload missing")
    client = MetaConversionsApiClient()
    return await client.send_events(payload)


async def process_meta_outbox_operation(db, operation_key: str, worker_id: str | None = None) -> bool:
    if not is_meta_enabled():
        return False
    worker = worker_id or build_meta_worker_id("meta-once")
    event = await outbox_service.claim_event(db, operation_key=operation_key, provider=META_PROVIDER, worker_id=worker)
    if not event:
        return False
    try:
        await _send_meta_event_for_outbox(db, event)
    except MetaPermanentError as exc:
        await outbox_service.mark_failed(db, event["_id"], last_error=str(exc), retryable=False)
        return False
    except (MetaRetryableError, MetaDisabledError) as exc:
        await outbox_service.mark_failed(
            db,
            event["_id"],
            last_error=str(exc),
            retryable=True,
            retry_after_seconds=getattr(exc, "retry_after_seconds", None),
        )
        return False
    await outbox_service.mark_sent(db, event["_id"])
    return True


async def process_due_meta_events(db, *, limit: int = 10, worker_id: str) -> int:
    if not is_meta_enabled():
        return 0
    processed = 0
    while processed < limit:
        event = await outbox_service.claim_next_due_event(db, provider=META_PROVIDER, worker_id=worker_id)
        if not event:
            break
        try:
            await _send_meta_event_for_outbox(db, event)
        except MetaPermanentError as exc:
            await outbox_service.mark_failed(db, event["_id"], last_error=str(exc), retryable=False)
        except (MetaRetryableError, MetaDisabledError) as exc:
            await outbox_service.mark_failed(
                db,
                event["_id"],
                last_error=str(exc),
                retryable=True,
                retry_after_seconds=getattr(exc, "retry_after_seconds", None),
            )
        else:
            await outbox_service.mark_sent(db, event["_id"])
        processed += 1
    return processed


async def run_meta_outbox_loop(db, *, poll_interval_seconds: int | None = None, worker_id: str | None = None) -> None:
    loop_poll_interval = poll_interval_seconds or settings.META_OUTBOX_POLL_INTERVAL_SECONDS
    loop_worker_id = worker_id or build_meta_worker_id()
    while True:
        try:
            await process_due_meta_events(db, limit=10, worker_id=loop_worker_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Unexpected error while processing Meta outbox")
        await asyncio.sleep(loop_poll_interval)
