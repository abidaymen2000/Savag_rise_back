import asyncio
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.domain.order_constants import OUTBOX_DEAD_LETTER, OUTBOX_FAILED, OUTBOX_PENDING, OUTBOX_PROCESSING, OUTBOX_SENT
from app.domain.order_errors import InsufficientStockError
from app.integrations.meta.client import MetaConversionsApiClient, MetaPermanentError, MetaRetryableError
from app.integrations.meta.hashing import normalize_email, normalize_phone, sha256_hexdigest
from app.integrations.meta.schemas import MetaEventContext
from app.integrations.meta.service import (
    build_complete_registration_payload,
    build_meta_context,
    build_purchase_payload,
    enqueue_purchase_event,
    process_meta_outbox_operation,
    process_due_meta_events,
)
from app.services.services_store import auth_service, order_domain_service, outbox_service


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, modified_count=1):
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self, docs=None, unique_rules=None):
        self.docs = list(docs or [])
        self.unique_rules = list(unique_rules or [])

    def _matches(self, doc, query):
        for key, value in query.items():
            if key == "$or":
                if not any(self._matches(doc, clause) for clause in value):
                    return False
                continue
            current = doc.get(key)
            if isinstance(value, dict):
                if "$in" in value and current not in value["$in"]:
                    return False
                if "$lte" in value:
                    if current is None or current > value["$lte"]:
                        return False
                if "$type" in value:
                    if value["$type"] == "string" and not isinstance(current, str):
                        return False
            elif current != value:
                return False
        return True

    def _check_unique(self, doc):
        for rule in self.unique_rules:
            if isinstance(rule, tuple):
                if all(doc.get(field) is not None for field in rule):
                    for existing in self.docs:
                        if all(existing.get(field) == doc.get(field) for field in rule):
                            raise DuplicateKeyError(f"duplicate key for {rule}")
            else:
                if doc.get(rule) is not None and any(existing.get(rule) == doc.get(rule) for existing in self.docs):
                    raise DuplicateKeyError(f"duplicate key for {rule}")

    async def find_one(self, query, projection=None, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, query):
                if projection:
                    projected = {}
                    include_id = projection.get("_id", 1) if isinstance(projection, dict) else 1
                    for key, enabled in projection.items():
                        if enabled and key in doc:
                            projected[key] = doc[key]
                    if include_id and "_id" in doc:
                        projected["_id"] = doc["_id"]
                    return projected
                return doc
        return None

    async def insert_one(self, doc, session=None):
        self._check_unique(doc)
        inserted = dict(doc)
        inserted.setdefault("_id", ObjectId())
        self.docs.append(inserted)
        return FakeInsertResult(inserted["_id"])

    async def update_one(self, query, update, *args, **kwargs):
        doc = await self.find_one(query)
        if not doc:
            return FakeUpdateResult(0)
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        for key, value in update.get("$inc", {}).items():
            doc[key] = int(doc.get(key, 0) or 0) + value
        return FakeUpdateResult(1)

    async def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self.docs.pop(index)
                break

    async def find_one_and_update(self, query, update, sort=None, **kwargs):
        candidates = [doc for doc in self.docs if self._matches(doc, query)]
        if not candidates:
            return None
        if sort:
            key, direction = sort[0]
            candidates.sort(key=lambda item: item.get(key), reverse=direction < 0)
        doc = candidates[0]
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        for key, value in update.get("$inc", {}).items():
            doc[key] = int(doc.get(key, 0) or 0) + value
        return doc


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    @asynccontextmanager
    async def start_transaction(self):
        yield self


class FakeDb:
    def __init__(self):
        self.collections = {
            "orders": FakeCollection(unique_rules=["idempotency_key"]),
            "order_idempotency": FakeCollection(unique_rules=["key"]),
            "outbox_events": FakeCollection(unique_rules=["operation_key", ("provider", "event_id")]),
            "users": FakeCollection(unique_rules=["email"]),
        }
        self.client = SimpleNamespace(start_session=self._start_session)

    async def _start_session(self):
        return FakeSession()

    def __getitem__(self, name):
        return self.collections[name]


class FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))


class FakeResponse:
    def __init__(self, status_code, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json


class FakeAsyncClient:
    def __init__(self, response=None, exc=None, timeout=None):
        self.response = response
        self.exc = exc
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        if self.exc:
            raise self.exc
        return self.response


class MetaHashingTests(unittest.TestCase):
    def test_normalize_email_lowercases_and_trims(self):
        self.assertEqual(normalize_email("  Jean.Doe@Example.COM "), "jean.doe@example.com")

    def test_normalize_tunisian_phone(self):
        self.assertEqual(normalize_phone("+216 21 461 637"), "21621461637")
        self.assertEqual(normalize_phone("21 461 637"), "21621461637")


class MetaPayloadTests(unittest.TestCase):
    def test_purchase_payload_for_guest_uses_persisted_order_data(self):
        order = {
            "_id": ObjectId(),
            "user_id": None,
            "user_email": None,
            "shipping": {
                "full_name": "Jane Guest",
                "email": None,
                "phone": "+216 21 461 637",
                "city": "Tunis",
                "country": "Tunisia",
            },
            "item_snapshots": [
                {"meta_content_id": "prod-1-black-m", "qty": 2, "unit_price_final": 64.995},
            ],
            "total_amount": 129.99,
            "created_at": datetime(2026, 6, 26, 10, 0, 0),
            "meta_context": {"event_source_url": "https://savagerise.com/checkout", "fbp": "fb.1.123.456"},
        }
        payload = build_purchase_payload(order, meta_context=MetaEventContext(client_ip_address="41.226.10.1", client_user_agent="Mozilla/5.0"))
        event = payload["data"][0]

        self.assertEqual(event["event_name"], "Purchase")
        self.assertEqual(event["event_id"], f"purchase:{order['_id']}")
        self.assertEqual(event["custom_data"]["currency"], "TND")
        self.assertEqual(event["custom_data"]["value"], 129.99)
        self.assertEqual(event["custom_data"]["content_ids"], ["prod-1-black-m"])
        self.assertEqual(event["custom_data"]["contents"][0]["item_price"], 65.0)
        self.assertNotIn("external_id", event["user_data"])
        self.assertEqual(event["user_data"]["ph"][0], sha256_hexdigest("21621461637"))

    def test_purchase_payload_for_connected_user_hashes_external_id(self):
        order = {
            "_id": ObjectId(),
            "user_id": "user-42",
            "user_email": "profile@example.com",
            "shipping": {
                "full_name": "Jane Buyer",
                "email": "order@example.com",
                "phone": "+21621461637",
                "city": "Tunis",
                "country": "Tunisia",
            },
            "item_snapshots": [],
            "total_amount": 10,
            "created_at": datetime(2026, 6, 26, 10, 0, 0),
            "meta_context": {},
        }
        payload = build_purchase_payload(order)
        self.assertEqual(payload["data"][0]["user_data"]["external_id"][0], sha256_hexdigest("user-42"))
        self.assertEqual(payload["data"][0]["user_data"]["em"][0], sha256_hexdigest("order@example.com"))

    def test_purchase_payload_ignores_frontend_purchase_event_id(self):
        order = {
            "_id": ObjectId(),
            "user_id": None,
            "shipping": {"full_name": "Guest Buyer", "phone": "+21621461637", "city": "Tunis", "country": "Tunisia"},
            "item_snapshots": [],
            "total_amount": 10,
            "created_at": datetime(2026, 6, 26, 10, 0, 0),
            "meta_context": {"event_id": "frontend-arbitrary"},
        }
        payload = build_purchase_payload(order)
        self.assertEqual(payload["data"][0]["event_id"], f"purchase:{order['_id']}")

    def test_complete_registration_payload_uses_stable_event_id(self):
        user = {
            "_id": ObjectId(),
            "email": "new@example.com",
            "full_name": "John Doe",
            "created_at": datetime(2026, 6, 26, 9, 0, 0),
            "meta_context": {"event_source_url": "https://savagerise.com/signup"},
        }
        payload = build_complete_registration_payload(user, meta_context=MetaEventContext(client_ip_address="41.0.0.1", client_user_agent="Mozilla/5.0"))
        self.assertEqual(payload["data"][0]["event_id"], f"registration:{user['_id']}")

    def test_test_event_code_only_present_when_configured(self):
        order = {
            "_id": ObjectId(),
            "shipping": {"full_name": "Jane Buyer", "phone": "+21621461637", "city": "Tunis", "country": "Tunisia"},
            "item_snapshots": [],
            "total_amount": 10,
            "created_at": datetime(2026, 6, 26, 10, 0, 0),
            "meta_context": {},
        }
        with patch("app.integrations.meta.service.settings.META_TEST_EVENT_CODE", "TEST123"):
            payload = build_purchase_payload(order)
        self.assertEqual(payload["test_event_code"], "TEST123")


class MetaClientRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_400_is_permanent(self):
        client = MetaConversionsApiClient()
        with (
            patch("app.integrations.meta.client.settings.META_CAPI_ENABLED", True),
            patch("app.integrations.meta.client.settings.META_PIXEL_ID", "123"),
            patch("app.integrations.meta.client.settings.META_CONVERSIONS_API_TOKEN", SimpleNamespace(get_secret_value=lambda: "token")),
            patch("app.integrations.meta.client.httpx.AsyncClient", return_value=FakeAsyncClient(response=FakeResponse(400))),
        ):
            with self.assertRaises(MetaPermanentError):
                await client.send_events({"data": []})

    async def test_http_401_is_permanent(self):
        client = MetaConversionsApiClient()
        with (
            patch("app.integrations.meta.client.settings.META_CAPI_ENABLED", True),
            patch("app.integrations.meta.client.settings.META_PIXEL_ID", "123"),
            patch("app.integrations.meta.client.settings.META_CONVERSIONS_API_TOKEN", SimpleNamespace(get_secret_value=lambda: "token")),
            patch("app.integrations.meta.client.httpx.AsyncClient", return_value=FakeAsyncClient(response=FakeResponse(401))),
        ):
            with self.assertRaises(MetaPermanentError):
                await client.send_events({"data": []})

    async def test_http_429_is_retryable(self):
        client = MetaConversionsApiClient()
        with (
            patch("app.integrations.meta.client.settings.META_CAPI_ENABLED", True),
            patch("app.integrations.meta.client.settings.META_PIXEL_ID", "123"),
            patch("app.integrations.meta.client.settings.META_CONVERSIONS_API_TOKEN", SimpleNamespace(get_secret_value=lambda: "token")),
            patch("app.integrations.meta.client.httpx.AsyncClient", return_value=FakeAsyncClient(response=FakeResponse(429, headers={"Retry-After": "7"}))),
        ):
            with self.assertRaises(MetaRetryableError) as ctx:
                await client.send_events({"data": []})
        self.assertEqual(ctx.exception.retry_after_seconds, 7)

    async def test_http_500_is_retryable(self):
        client = MetaConversionsApiClient()
        with (
            patch("app.integrations.meta.client.settings.META_CAPI_ENABLED", True),
            patch("app.integrations.meta.client.settings.META_PIXEL_ID", "123"),
            patch("app.integrations.meta.client.settings.META_CONVERSIONS_API_TOKEN", SimpleNamespace(get_secret_value=lambda: "token")),
            patch("app.integrations.meta.client.httpx.AsyncClient", return_value=FakeAsyncClient(response=FakeResponse(500))),
        ):
            with self.assertRaises(MetaRetryableError):
                await client.send_events({"data": []})

    async def test_timeout_is_retryable(self):
        client = MetaConversionsApiClient()
        with (
            patch("app.integrations.meta.client.settings.META_CAPI_ENABLED", True),
            patch("app.integrations.meta.client.settings.META_PIXEL_ID", "123"),
            patch("app.integrations.meta.client.settings.META_CONVERSIONS_API_TOKEN", SimpleNamespace(get_secret_value=lambda: "token")),
            patch("app.integrations.meta.client.httpx.AsyncClient", return_value=FakeAsyncClient(exc=TimeoutError())),
            patch("app.integrations.meta.client.httpx.TimeoutException", TimeoutError),
            patch("app.integrations.meta.client.httpx.NetworkError", ConnectionError),
        ):
            with self.assertRaises(MetaRetryableError):
                await client.send_events({"data": []})


class OutboxLockingTests(unittest.IsolatedAsyncioTestCase):
    async def test_claim_is_atomic_between_two_workers(self):
        db = FakeDb()
        now = datetime.utcnow()
        db["outbox_events"].docs.append(
            {
                "_id": ObjectId(),
                "provider": "meta",
                "event_id": "purchase:1",
                "operation_key": "meta:purchase:1",
                "payload_json": {"data": [{"event_time": 111}]},
                "status": OUTBOX_PENDING,
                "attempts": 0,
                "max_attempts": 5,
                "created_at": now,
                "next_retry_at": None,
                "locked_at": None,
                "locked_by": None,
            }
        )

        first = await outbox_service.claim_next_due_event(db, provider="meta", worker_id="worker-a")
        second = await outbox_service.claim_next_due_event(db, provider="meta", worker_id="worker-b")

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(first["locked_by"], "worker-a")

    async def test_stale_processing_lock_can_be_recovered(self):
        db = FakeDb()
        stale_time = datetime.utcnow() - timedelta(seconds=1000)
        db["outbox_events"].docs.append(
            {
                "_id": ObjectId(),
                "provider": "meta",
                "event_id": "purchase:2",
                "operation_key": "meta:purchase:2",
                "payload_json": {"data": [{"event_time": 222}]},
                "status": OUTBOX_PROCESSING,
                "attempts": 1,
                "max_attempts": 5,
                "created_at": stale_time,
                "next_retry_at": None,
                "locked_at": stale_time,
                "locked_by": "dead-worker",
            }
        )

        claimed = await outbox_service.claim_next_due_event(db, provider="meta", worker_id="worker-b")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["locked_by"], "worker-b")
        self.assertEqual(claimed["attempts"], 2)

    async def test_mark_failed_moves_to_dead_letter_after_max_attempts(self):
        db = FakeDb()
        outbox_id = ObjectId()
        db["outbox_events"].docs.append(
            {
                "_id": outbox_id,
                "provider": "meta",
                "event_id": "purchase:3",
                "operation_key": "meta:purchase:3",
                "payload_json": {"data": [{"event_time": 333}]},
                "status": OUTBOX_PROCESSING,
                "attempts": 5,
                "max_attempts": 5,
                "created_at": datetime.utcnow(),
                "next_retry_at": None,
                "locked_at": datetime.utcnow(),
                "locked_by": "worker-a",
            }
        )

        await outbox_service.mark_failed(db, outbox_id, last_error="Meta returned 500", retryable=True)
        self.assertEqual(db["outbox_events"].docs[0]["status"], OUTBOX_DEAD_LETTER)


class MetaOutboxProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry_uses_same_payload_json_and_event_time(self):
        db = FakeDb()
        order_id = ObjectId()
        original_payload = {
            "data": [
                {
                    "event_name": "Purchase",
                    "event_id": f"purchase:{order_id}",
                    "event_time": 1719396000,
                    "user_data": {"ph": ["hash"]},
                    "custom_data": {"value": 50.0, "currency": "TND", "order_id": str(order_id), "content_type": "product", "content_ids": [], "contents": [], "num_items": 0},
                }
            ]
        }
        db["outbox_events"].docs.append(
            {
                "_id": ObjectId(),
                "provider": "meta",
                "event_id": f"purchase:{order_id}",
                "operation_key": f"meta:purchase:{order_id}",
                "aggregate_type": "order",
                "aggregate_id": str(order_id),
                "payload_json": original_payload,
                "status": OUTBOX_PENDING,
                "attempts": 0,
                "max_attempts": 5,
                "created_at": datetime.utcnow(),
                "next_retry_at": None,
                "locked_at": None,
                "locked_by": None,
            }
        )
        sent_payloads = []

        async def capture_send(payload):
            sent_payloads.append(payload)
            return {"events_received": 1}

        with patch("app.integrations.meta.service.is_meta_enabled", return_value=True), patch.object(
            MetaConversionsApiClient, "send_events", AsyncMock(side_effect=capture_send)
        ):
            result = await process_meta_outbox_operation(db, f"meta:purchase:{order_id}", worker_id="worker-a")

        self.assertTrue(result)
        self.assertEqual(sent_payloads[0]["data"][0]["event_time"], 1719396000)
        self.assertEqual(db["outbox_events"].docs[0]["status"], OUTBOX_SENT)

    async def test_retryable_failure_sets_failed_status(self):
        db = FakeDb()
        outbox_id = ObjectId()
        db["outbox_events"].docs.append(
            {
                "_id": outbox_id,
                "provider": "meta",
                "event_id": "purchase:retry",
                "operation_key": "meta:purchase:retry",
                "aggregate_type": "order",
                "aggregate_id": str(ObjectId()),
                "payload_json": {"data": [{"event_time": 123}]},
                "status": OUTBOX_PENDING,
                "attempts": 0,
                "max_attempts": 5,
                "created_at": datetime.utcnow(),
                "next_retry_at": None,
                "locked_at": None,
                "locked_by": None,
            }
        )
        with patch("app.integrations.meta.service.is_meta_enabled", return_value=True), patch.object(
            MetaConversionsApiClient, "send_events", AsyncMock(side_effect=MetaRetryableError("Meta rate limit", retry_after_seconds=9))
        ):
            result = await process_meta_outbox_operation(db, "meta:purchase:retry", worker_id="worker-a")

        self.assertFalse(result)
        self.assertEqual(db["outbox_events"].docs[0]["status"], OUTBOX_FAILED)
        self.assertIsNotNone(db["outbox_events"].docs[0]["next_retry_at"])

    async def test_permanent_failure_sets_dead_letter(self):
        db = FakeDb()
        outbox_id = ObjectId()
        db["outbox_events"].docs.append(
            {
                "_id": outbox_id,
                "provider": "meta",
                "event_id": "purchase:dead",
                "operation_key": "meta:purchase:dead",
                "aggregate_type": "order",
                "aggregate_id": str(ObjectId()),
                "payload_json": {"data": [{"event_time": 123}]},
                "status": OUTBOX_PENDING,
                "attempts": 0,
                "max_attempts": 5,
                "created_at": datetime.utcnow(),
                "next_retry_at": None,
                "locked_at": None,
                "locked_by": None,
            }
        )
        with patch("app.integrations.meta.service.is_meta_enabled", return_value=True), patch.object(
            MetaConversionsApiClient, "send_events", AsyncMock(side_effect=MetaPermanentError("Meta validation error (400)"))
        ):
            result = await process_meta_outbox_operation(db, "meta:purchase:dead", worker_id="worker-a")

        self.assertFalse(result)
        self.assertEqual(db["outbox_events"].docs[0]["status"], OUTBOX_DEAD_LETTER)


class MetaOrderFlowTests(unittest.IsolatedAsyncioTestCase):
    def _build_order_input(self):
        return SimpleNamespace(
            model_dump=lambda mode="json": {"shipping": {"email": None}, "meta": {"event_id": "frontend-bad"}},
            shipping=SimpleNamespace(
                email=None,
                model_dump=lambda: {
                    "full_name": "Guest Buyer",
                    "email": None,
                    "phone": "+21621461637",
                    "address_line1": "1 rue",
                    "postal_code": "1000",
                    "city": "Tunis",
                    "country": "Tunisia",
                },
            ),
            items=[],
            payment_method="cod",
            loyalty_points_to_use=0,
            meta={"event_id": "frontend-bad", "event_source_url": "https://savagerise.com/checkout"},
        )

    async def test_create_order_enqueues_guest_purchase_after_successful_commit(self):
        db = FakeDb()
        background_tasks = FakeBackgroundTasks()
        order_in = self._build_order_input()
        quote = {
            "pack_items": [],
            "item_snapshots": [{"meta_content_id": "prod-1", "qty": 3, "unit_price_final": 10.0}],
            "inventory_allocations": [],
            "subtotal": 30.0,
            "discount_value": 0.0,
            "pack_discount_value": 0.0,
            "promo_code": None,
            "loyalty_points_used": 0,
            "loyalty_discount_value": 0.0,
            "total_amount": 37.0,
            "shipping_amount": 7.0,
            "shipping_rate_id": "sr-1",
            "shipping_rate_name": "Standard",
        }
        request = SimpleNamespace(
            url="https://api.savagerise.com/orders",
            cookies={},
            query_params={},
            headers={"user-agent": "Mozilla/5.0", "x-forwarded-for": "198.51.100.24"},
            client=SimpleNamespace(host="10.0.0.1"),
        )

        with (
            patch.object(order_domain_service, "quote_order", AsyncMock(return_value=quote)),
            patch.object(order_domain_service, "_reserve_allocation", AsyncMock()),
            patch.object(order_domain_service, "append_history", AsyncMock()),
            patch.object(order_domain_service, "track_event", AsyncMock()),
            patch("app.integrations.meta.service.is_meta_enabled", return_value=True),
        ):
            result = await order_domain_service.create_order(db, order_in, background_tasks, request, None, idempotency_key="idem-meta-1")

        self.assertTrue(result["is_guest"])
        meta_events = [doc for doc in db["outbox_events"].docs if doc.get("provider") == "meta"]
        self.assertEqual(len(meta_events), 1)
        self.assertEqual(meta_events[0]["event_id"], f"purchase:{result['id']}")
        self.assertEqual(meta_events[0]["event_name"], "Purchase")
        self.assertEqual(meta_events[0]["payload_json"]["data"][0]["custom_data"]["num_items"], 3)
        self.assertNotIn("external_id", meta_events[0]["payload_json"]["data"][0]["user_data"])
        self.assertEqual(len(background_tasks.tasks), 1)

    async def test_create_order_connected_user_hashes_external_id(self):
        db = FakeDb()
        background_tasks = FakeBackgroundTasks()
        order_in = self._build_order_input()
        quote = {
            "pack_items": [],
            "item_snapshots": [],
            "inventory_allocations": [],
            "subtotal": 10.0,
            "discount_value": 0.0,
            "pack_discount_value": 0.0,
            "promo_code": None,
            "loyalty_points_used": 0,
            "loyalty_discount_value": 0.0,
            "total_amount": 17.0,
            "shipping_amount": 7.0,
            "shipping_rate_id": "sr-1",
            "shipping_rate_name": "Standard",
        }
        current_user = {"_id": "user-123", "email": "profile@example.com"}

        with (
            patch.object(order_domain_service, "quote_order", AsyncMock(return_value=quote)),
            patch.object(order_domain_service, "_reserve_allocation", AsyncMock()),
            patch.object(order_domain_service, "append_history", AsyncMock()),
            patch.object(order_domain_service, "track_event", AsyncMock()),
            patch("app.integrations.meta.service.is_meta_enabled", return_value=True),
        ):
            result = await order_domain_service.create_order(db, order_in, background_tasks, None, current_user, idempotency_key="idem-meta-2")

        meta_event = next(doc for doc in db["outbox_events"].docs if doc.get("provider") == "meta")
        self.assertEqual(meta_event["payload_json"]["data"][0]["user_data"]["external_id"][0], sha256_hexdigest("user-123"))
        self.assertEqual(meta_event["event_id"], f"purchase:{result['id']}")

    async def test_create_order_does_not_enqueue_meta_when_stock_fails(self):
        db = FakeDb()
        background_tasks = FakeBackgroundTasks()
        order_in = self._build_order_input()
        quote = {
            "pack_items": [],
            "item_snapshots": [],
            "inventory_allocations": [{"product_id": "prod-1", "color": "Black", "size": "M", "qty": 1}],
            "subtotal": 100.0,
            "discount_value": 0.0,
            "pack_discount_value": 0.0,
            "promo_code": None,
            "loyalty_points_used": 0,
            "loyalty_discount_value": 0.0,
            "total_amount": 107.0,
            "shipping_amount": 7.0,
            "shipping_rate_id": "sr-1",
            "shipping_rate_name": "Standard",
        }

        with (
            patch.object(order_domain_service, "quote_order", AsyncMock(return_value=quote)),
            patch.object(order_domain_service, "_reserve_allocation", AsyncMock(side_effect=InsufficientStockError("stock"))),
            patch.object(order_domain_service, "append_history", AsyncMock()),
        ):
            with self.assertRaises(InsufficientStockError):
                await order_domain_service.create_order(db, order_in, background_tasks, None, None, idempotency_key="idem-meta-3")

        self.assertEqual([doc for doc in db["outbox_events"].docs if doc.get("provider") == "meta"], [])

    async def test_enqueue_purchase_event_is_deduplicated(self):
        db = FakeDb()
        order = {
            "_id": ObjectId(),
            "user_id": None,
            "shipping": {"full_name": "Guest Buyer", "phone": "+21621461637", "city": "Tunis", "country": "Tunisia"},
            "item_snapshots": [],
            "total_amount": 10,
            "created_at": datetime.utcnow(),
        }
        with patch("app.integrations.meta.service.is_meta_enabled", return_value=True):
            first = await enqueue_purchase_event(db, order)
            second = await enqueue_purchase_event(db, order)
        self.assertTrue(first)
        self.assertFalse(second)


class MetaSignupTests(unittest.IsolatedAsyncioTestCase):
    async def test_signup_schedules_complete_registration_after_user_creation(self):
        db = FakeDb()
        created_user = {
            "_id": ObjectId(),
            "email": "new@example.com",
            "full_name": "John Doe",
            "is_active": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        user_in = SimpleNamespace(email="new@example.com", full_name="John Doe", meta=None)
        background_tasks = FakeBackgroundTasks()
        request = SimpleNamespace(
            url="https://api.savagerise.com/auth/signup",
            cookies={},
            query_params={},
            headers={"user-agent": "Mozilla/5.0", "x-forwarded-for": "198.51.100.11"},
            client=SimpleNamespace(host="10.0.0.1"),
        )

        with (
            patch.object(auth_service.user_crud, "get_user_by_email", AsyncMock(return_value=None)),
            patch.object(auth_service.user_crud, "create_user", AsyncMock(return_value=created_user)),
            patch.object(auth_service, "send_email"),
            patch.object(auth_service, "track_event", AsyncMock()),
            patch("app.integrations.meta.service.is_meta_enabled", return_value=True),
        ):
            await auth_service.signup(db, user_in, background_tasks, request)

        meta_events = [args for func, args, kwargs in background_tasks.tasks if getattr(func, "__name__", "") == "process_meta_outbox_operation"]
        self.assertEqual(len(meta_events), 1)
        outbox_events = [doc for doc in db["outbox_events"].docs if doc.get("provider") == "meta"]
        self.assertEqual(len(outbox_events), 1)


class MetaIpTests(unittest.TestCase):
    def test_build_meta_context_uses_trusted_proxy_chain(self):
        request = SimpleNamespace(
            url="https://api.savagerise.com/orders",
            cookies={},
            query_params={},
            headers={"user-agent": "Mozilla/5.0", "x-forwarded-for": "203.0.113.9, 198.51.100.3"},
            client=SimpleNamespace(host="10.0.0.1"),
        )
        with patch("app.analytics.utils.settings.TRUSTED_PROXY_HOPS", 1), patch("app.analytics.utils.settings.TRUST_PROXY_HEADERS", True):
            context = build_meta_context(request, {})
        self.assertEqual(context.client_ip_address, "198.51.100.3")

    def test_build_meta_context_falls_back_when_forwarded_header_invalid(self):
        request = SimpleNamespace(
            url="https://api.savagerise.com/orders",
            cookies={},
            query_params={},
            headers={"user-agent": "Mozilla/5.0", "x-forwarded-for": "garbage"},
            client=SimpleNamespace(host="10.0.0.1"),
        )
        context = build_meta_context(request, {})
        self.assertEqual(context.client_ip_address, "10.0.0.1")


if __name__ == "__main__":
    unittest.main()
