import unittest
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.domain.order_errors import InsufficientStockError
from app.integrations.meta.hashing import normalize_email, normalize_phone, sha256_hexdigest
from app.integrations.meta.service import (
    build_complete_registration_payload,
    build_purchase_payload,
    enqueue_purchase_event,
)
from app.services.services_store import auth_service, order_domain_service


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
            if isinstance(value, dict):
                if "$in" in value and doc.get(key) not in value["$in"]:
                    return False
                if "$lte" in value and not (doc.get(key) is not None and doc.get(key) <= value["$lte"]):
                    return False
            elif doc.get(key) != value:
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

    async def find_one(self, query, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, query):
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
            "users": FakeCollection(),
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
                {
                    "meta_content_id": "prod-1-black-m",
                    "qty": 2,
                    "unit_price_final": 64.995,
                }
            ],
            "total_amount": 129.99,
            "created_at": datetime(2026, 6, 26, 10, 0, 0),
            "meta_context": {
                "event_source_url": "https://savagerise.com/checkout",
                "client_ip_address": "41.226.10.1",
                "client_user_agent": "Mozilla/5.0",
                "fbp": "fb.1.123.456",
            },
        }
        payload = build_purchase_payload(order)
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
            "user_email": "buyer@example.com",
            "shipping": {
                "full_name": "Jane Buyer",
                "email": "stale@example.com",
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
        self.assertEqual(payload["data"][0]["user_data"]["em"][0], sha256_hexdigest("buyer@example.com"))

    def test_complete_registration_payload_uses_stable_event_id(self):
        user = {
            "_id": ObjectId(),
            "email": "new@example.com",
            "full_name": "John Doe",
            "created_at": datetime(2026, 6, 26, 9, 0, 0),
            "meta_context": {
                "event_source_url": "https://savagerise.com/signup",
                "client_ip_address": "41.0.0.1",
                "client_user_agent": "Mozilla/5.0",
            },
        }
        payload = build_complete_registration_payload(user)
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


class MetaOrderFlowTests(unittest.IsolatedAsyncioTestCase):
    def _build_order_input(self):
        return SimpleNamespace(
            model_dump=lambda mode="json": {"shipping": {"email": None}},
            shipping=SimpleNamespace(model_dump=lambda: {"full_name": "Guest Buyer", "email": None, "phone": "+21621461637", "address_line1": "1 rue", "postal_code": "1000", "city": "Tunis", "country": "Tunisia"}),
            items=[],
            payment_method="cod",
            loyalty_points_to_use=0,
            meta={"event_source_url": "https://savagerise.com/checkout"},
        )

    async def test_create_order_enqueues_meta_after_successful_commit(self):
        db = FakeDb()
        background_tasks = FakeBackgroundTasks()
        order_in = self._build_order_input()
        quote = {
            "pack_items": [],
            "item_snapshots": [],
            "inventory_allocations": [],
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
        request = SimpleNamespace(
            url="https://api.savagerise.com/orders",
            cookies={},
            query_params={},
            headers={"user-agent": "Mozilla/5.0", "x-forwarded-for": "41.226.1.10"},
            client=SimpleNamespace(host="10.0.0.1"),
        )

        with (
            patch.object(order_domain_service, "quote_order", AsyncMock(return_value=quote)),
            patch.object(order_domain_service, "_reserve_allocation", AsyncMock()),
            patch.object(order_domain_service, "append_history", AsyncMock()),
            patch.object(order_domain_service, "track_event", AsyncMock()),
            patch.object(order_domain_service, "enqueue_purchase_event", AsyncMock(side_effect=enqueue_purchase_event)),
            patch("app.integrations.meta.service.is_meta_enabled", return_value=True),
        ):
            result = await order_domain_service.create_order(db, order_in, background_tasks, request, None, idempotency_key="idem-meta-1")

        self.assertEqual(result["is_guest"], True)
        meta_events = [doc for doc in db["outbox_events"].docs if doc.get("provider") == "meta"]
        self.assertEqual(len(meta_events), 1)
        self.assertEqual(meta_events[0]["event_id"], f"purchase:{result['id']}")
        self.assertEqual(len(background_tasks.tasks), 1)

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
                await order_domain_service.create_order(db, order_in, background_tasks, None, None, idempotency_key="idem-meta-2")

        self.assertEqual([doc for doc in db["outbox_events"].docs if doc.get("provider") == "meta"], [])


class MetaSignupTests(unittest.IsolatedAsyncioTestCase):
    async def test_signup_schedules_complete_registration_after_user_creation(self):
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
        request = SimpleNamespace(url="https://api.savagerise.com/auth/signup", cookies={}, query_params={}, headers={"user-agent": "Mozilla/5.0"})
        request.client = None

        with (
            patch.object(auth_service.user_crud, "get_user_by_email", AsyncMock(return_value=None)),
            patch.object(auth_service.user_crud, "create_user", AsyncMock(return_value=created_user)),
            patch.object(auth_service, "send_email"),
            patch.object(auth_service, "track_event", AsyncMock()),
            patch.object(auth_service, "enqueue_complete_registration_event", AsyncMock(return_value=True)),
        ):
            await auth_service.signup(SimpleNamespace(), user_in, background_tasks, request)

        task_names = [getattr(func, "__name__", str(func)) for func, _, _ in background_tasks.tasks]
        self.assertIn("process_meta_outbox_operation", task_names)


if __name__ == "__main__":
    unittest.main()
