import unittest
import types
import sys

fastapi_stub = types.ModuleType("fastapi")


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


fastapi_stub.HTTPException = HTTPException
fastapi_stub.status = types.SimpleNamespace(
    HTTP_409_CONFLICT=409,
    HTTP_400_BAD_REQUEST=400,
    HTTP_404_NOT_FOUND=404,
)
sys.modules.setdefault("fastapi", fastapi_stub)

from app.domain.inventory import inventory_projection, stock_available_value
from app.domain.order_errors import InvalidOrderTransitionError
from app.domain.order_state_machine import ensure_order_transition, fulfillment_status_for_order_status, payment_status_after_refund
from scripts.migrate_inventory_model import migrate_variant_sizes


class OrderDomainUnitTests(unittest.TestCase):
    def test_inventory_projection_from_stock_on_hand(self):
        row = inventory_projection({"size": "M", "stock_on_hand": 7})
        self.assertEqual(row["stock_on_hand"], 7)
        self.assertEqual(row["stock_reserved"], 0)
        self.assertEqual(row["stock_available"], 7)

    def test_inventory_projection_with_reserved(self):
        row = inventory_projection({"size": "L", "stock_on_hand": 10, "stock_reserved": 4})
        self.assertEqual(stock_available_value(row), 6)

    def test_valid_order_transition(self):
        ensure_order_transition("pending", "confirmed")
        ensure_order_transition("confirmed", "preparing")
        ensure_order_transition("shipped", "delivered")

    def test_invalid_order_transition(self):
        with self.assertRaises(InvalidOrderTransitionError):
            ensure_order_transition("cancelled", "paid")

    def test_refund_status_full_vs_partial(self):
        self.assertEqual(payment_status_after_refund(100, 100), "refunded")
        self.assertEqual(payment_status_after_refund(40, 100), "partially_refunded")

    def test_fulfillment_status_mapping(self):
        self.assertEqual(fulfillment_status_for_order_status("pending", None), "reserved")
        self.assertEqual(fulfillment_status_for_order_status("preparing", "reserved"), "processing")
        self.assertEqual(fulfillment_status_for_order_status("cancelled", "reserved"), "cancelled")
        self.assertEqual(fulfillment_status_for_order_status("return_received", "returning"), "returned")

    def test_migrate_variant_sizes_preserves_total_stock(self):
        product = {
            "variants": [
                {
                    "color": "Black",
                    "sizes": [
                        {"size": "M", "stock": 3},
                        {"size": "L", "stock": 5},
                    ],
                }
            ]
        }
        variants, stats = migrate_variant_sizes(product)
        self.assertTrue(stats["changed"])
        self.assertEqual(stats["total_before"], 8)
        self.assertEqual(stats["total_after"], 8)
        self.assertEqual(variants[0]["sizes"][0]["stock_on_hand"], 3)
        self.assertEqual(variants[0]["sizes"][1]["stock_reserved"], 0)


if __name__ == "__main__":
    unittest.main()
