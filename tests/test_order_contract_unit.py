import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from fastapi import FastAPI
from pymongo.errors import DuplicateKeyError

from app.domain.order_errors import InvalidIdempotencyKeyReuseError
from app.domain.order_errors import InsufficientStockError
from app.routers.routers_store.orders import router as orders_router
from app.schemas.order import OrderCreate, OrderOut
from app.schemas.variant import SizeStockOut
from app.services.services_store import order_domain_service


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, modified_count=1):
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self, docs=None, unique_fields=None):
        self.docs = list(docs or [])
        self.unique_fields = tuple(unique_fields or [])

    async def find_one(self, query, *args, **kwargs):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None

    async def insert_one(self, doc, session=None):
        for field in self.unique_fields:
            if field in doc and any(existing.get(field) == doc[field] for existing in self.docs):
                raise DuplicateKeyError(f"duplicate key for {field}")
        self.docs.append(dict(doc))
        inserted_id = doc.get("_id", ObjectId())
        if "_id" not in self.docs[-1]:
            self.docs[-1]["_id"] = inserted_id
        return FakeInsertResult(inserted_id)

    async def update_one(self, query, update, *args, **kwargs):
        doc = await self.find_one(query)
        if not doc:
            return FakeUpdateResult(0)
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        return FakeUpdateResult(1)

    async def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if all(doc.get(key) == value for key, value in query.items()):
                self.docs.pop(index)
                return


class FakeDb:
    def __init__(self, orders=None, markers=None):
        self.collections = {
            "orders": FakeCollection(orders, unique_fields=["idempotency_key"]),
            "order_idempotency": FakeCollection(markers, unique_fields=["key"]),
        }
        self.client = SimpleNamespace()

    def __getitem__(self, name):
        return self.collections[name]


class OrderContractUnitTests(unittest.IsolatedAsyncioTestCase):
    def _build_order_payload(self):
        return {
            "items": [
                {
                    "product_id": "prod-1",
                    "color": "Black",
                    "size": "M",
                    "qty": 2,
                    "unit_price": 1.0,
                }
            ],
            "pack_items": [
                {
                    "pack_id": str(ObjectId()),
                    "qty": 1,
                    "items": [
                        {
                            "component_id": "c1",
                            "product_id": "prod-1",
                            "color": "Black",
                            "size": "M",
                            "qty": 1,
                            "unit_price": 0.01,
                        },
                        {
                            "component_id": "c2",
                            "product_id": "prod-2",
                            "color": "Black",
                            "size": "L",
                            "qty": 1,
                            "unit_price": 0.01,
                        },
                    ],
                }
            ],
            "shipping": {
                "full_name": "Jean Dupont",
                "email": "jean@example.com",
                "phone": "+21621461637",
                "address_line1": "12 rue de la Paix",
                "postal_code": "1000",
                "city": "Tunis",
                "country": "Tunisia",
            },
            "payment_method": "cod",
            "loyalty_points_to_use": 0,
        }

    async def test_order_create_ignores_client_prices(self):
        payload = self._build_order_payload()
        order_in = OrderCreate.model_validate(payload)

        self.assertNotIn("unit_price", order_in.items[0].model_dump())
        self.assertNotIn("unit_price", order_in.pack_items[0].items[0].model_dump())

    async def test_quote_uses_backend_prices_and_has_no_side_effects(self):
        order_in = OrderCreate.model_validate(self._build_order_payload())
        pack_id = str(ObjectId())
        order_in.pack_items[0].pack_id = pack_id
        fake_db = FakeDb()

        async def fake_find_product_snapshot(db, product_id):
            price = 50.0 if product_id == "prod-1" else 30.0
            return {
                "_id": product_id,
                "price": price,
                "sku": f"SKU-{product_id}",
                "name": f"Product {product_id}",
                "full_name": f"Product {product_id}",
                "variants": [
                    {
                        "color": "Black",
                        "sizes": [
                            {"size": "M", "stock_on_hand": 10, "stock_reserved": 0},
                            {"size": "L", "stock_on_hand": 10, "stock_reserved": 0},
                        ],
                    }
                ],
            }

        async def fake_pack(db, oid):
            return {
                "_id": ObjectId(pack_id),
                "title": "Starter Pack",
                "status": "active",
                "discount_type": "fixed_amount",
                "discount_value": 10,
                "components": [
                    {"id": "c1", "product_id": "prod-1", "qty": 1},
                    {"id": "c2", "product_id": "prod-2", "qty": 1},
                ],
            }

        with (
            patch.object(order_domain_service, "_find_product_snapshot", side_effect=fake_find_product_snapshot),
            patch.object(order_domain_service.pack_crud, "find_pack_by_id", side_effect=fake_pack),
            patch.object(order_domain_service, "resolve_shipping_rate", AsyncMock(return_value={"shipping_amount": 7.0, "shipping_rate_id": "sr-1", "shipping_rate_name": "Standard"})),
        ):
            quote = await order_domain_service.quote_order(fake_db, order_in, None)

        self.assertEqual(quote["subtotal"], 180.0)
        self.assertEqual(quote["pack_discount"], 10.0)
        self.assertEqual(quote["shipping_amount"], 7.0)
        self.assertEqual(quote["total"], 177.0)
        self.assertEqual(quote["items"][0]["unit_price_original"], 50.0)
        self.assertEqual(quote["items"][1]["discount_amount"] + quote["items"][2]["discount_amount"], 10.0)
        self.assertEqual(len(fake_db["orders"].docs), 0)
        self.assertEqual(len(fake_db["order_idempotency"].docs), 0)

    async def test_quote_fails_when_requested_quantity_exceeds_available_stock(self):
        order_in = OrderCreate.model_validate(self._build_order_payload())
        fake_db = FakeDb()

        async def fake_find_product_snapshot(db, product_id):
            return {
                "_id": product_id,
                "price": 50.0,
                "sku": f"SKU-{product_id}",
                "name": f"Product {product_id}",
                "full_name": f"Product {product_id}",
                "variants": [
                    {
                        "color": "Black",
                        "sizes": [
                            {"size": "M", "stock_on_hand": 1, "stock_reserved": 0},
                        ],
                    }
                ],
            }

        with patch.object(order_domain_service, "_find_product_snapshot", side_effect=fake_find_product_snapshot):
            with self.assertRaisesRegex(InsufficientStockError, "Stock insuffisant pour Black/M"):
                await order_domain_service.quote_order(fake_db, order_in, None)

    async def test_same_idempotency_key_same_payload_returns_existing_order(self):
        order_id = ObjectId()
        now = datetime.utcnow()
        existing_order = {
            "_id": order_id,
            "idempotency_key": "idem-1",
            "payload_hash": "hash-1",
            "shipping": self._build_order_payload()["shipping"],
            "items": [{"product_id": "prod-1", "color": "Black", "size": "M", "qty": 2}],
            "pack_items": [],
            "item_snapshots": [],
            "inventory_allocations": [],
            "payment_method": "cod",
            "payment_status": "unpaid",
            "fulfillment_status": "reserved",
            "subtotal": 100.0,
            "discount_value": 0.0,
            "pack_discount_value": 0.0,
            "loyalty_points_to_use": 0,
            "loyalty_points_used": 0,
            "loyalty_discount_value": 0.0,
            "loyalty_eligible_amount": 100.0,
            "loyalty_points_earned": 0,
            "loyalty_points_awarded": False,
            "shipping_amount": 7.0,
            "shipping_rate_id": "sr-1",
            "shipping_rate_name": "Standard",
            "total_amount": 107.0,
            "refunded_amount": 0.0,
            "status": "pending",
            "order_status": "pending",
            "is_guest": True,
            "created_at": now,
            "updated_at": now,
        }
        marker = {
            "key": "idem-1",
            "payload_hash": "hash-1",
            "status": "completed",
            "order_id": str(order_id),
            "created_at": now,
            "updated_at": now,
        }
        fake_db = FakeDb(orders=[existing_order], markers=[marker])
        order_in = OrderCreate.model_validate(self._build_order_payload())

        with patch.object(order_domain_service, "_payload_hash", return_value="hash-1"):
            result = await order_domain_service.create_order(fake_db, order_in, None, None, None, idempotency_key="idem-1")

        self.assertEqual(result["id"], str(order_id))
        self.assertEqual(len(fake_db["orders"].docs), 1)

    async def test_same_idempotency_key_different_payload_raises_conflict(self):
        now = datetime.utcnow()
        fake_db = FakeDb(
            markers=[
                {
                    "key": "idem-2",
                    "payload_hash": "hash-a",
                    "status": "completed",
                    "order_id": str(ObjectId()),
                    "created_at": now,
                    "updated_at": now,
                }
            ]
        )
        order_in = OrderCreate.model_validate(self._build_order_payload())

        with patch.object(order_domain_service, "_payload_hash", return_value="hash-b"):
            with self.assertRaises(InvalidIdempotencyKeyReuseError):
                await order_domain_service.create_order(fake_db, order_in, None, None, None, idempotency_key="idem-2")

    async def test_same_idempotency_key_in_progress_raises_conflict(self):
        now = datetime.utcnow()
        fake_db = FakeDb(
            markers=[
                {
                    "key": "idem-3",
                    "payload_hash": "hash-a",
                    "status": "in_progress",
                    "created_at": now,
                    "updated_at": now,
                }
            ]
        )
        order_in = OrderCreate.model_validate(self._build_order_payload())

        with patch.object(order_domain_service, "_payload_hash", return_value="hash-a"):
            with self.assertRaisesRegex(Exception, "deja en cours"):
                await order_domain_service.create_order(fake_db, order_in, None, None, None, idempotency_key="idem-3")


class OrderSchemaContractTests(unittest.TestCase):
    def test_order_out_requires_matching_status_alias(self):
        now = datetime.utcnow()
        with self.assertRaises(ValueError):
            OrderOut.model_validate(
                {
                    "id": "order-1",
                    "shipping": {
                        "full_name": "Jean Dupont",
                        "email": "jean@example.com",
                        "phone": "+21621461637",
                        "address_line1": "12 rue de la Paix",
                        "postal_code": "1000",
                        "city": "Tunis",
                        "country": "Tunisia",
                    },
                    "items": [],
                    "pack_items": [],
                    "item_snapshots": [],
                    "inventory_allocations": [],
                    "payment_method": "cod",
                    "payment_status": "unpaid",
                    "fulfillment_status": "reserved",
                    "total_amount": 0,
                    "status": "pending",
                    "order_status": "confirmed",
                    "created_at": now,
                    "updated_at": now,
                }
            )

    def test_openapi_exposes_order_contracts(self):
        app = FastAPI()
        app.include_router(orders_router)
        openapi = app.openapi()

        create_schema = openapi["components"]["schemas"]["OrderItemCreate"]
        quote_response = openapi["paths"]["/orders/quote"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        create_operation = openapi["paths"]["/orders/"]["post"]
        header_param = next(param for param in create_operation["parameters"] if param["name"] == "Idempotency-Key")

        self.assertNotIn("unit_price", create_schema["properties"])
        self.assertEqual(header_param["required"], True)
        self.assertIn("OrderQuoteOut", quote_response["$ref"])

    def test_variant_size_schema_still_exposes_stock_triplet(self):
        schema = SizeStockOut.model_json_schema()

        self.assertIn("stock_on_hand", schema["properties"])
        self.assertIn("stock_reserved", schema["properties"])
        self.assertIn("stock_available", schema["properties"])


if __name__ == "__main__":
    unittest.main()
