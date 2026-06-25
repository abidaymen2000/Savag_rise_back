import csv
import io

from fastapi import Response

from app.crud import inventory as inventory_crud
from app.crud import order as order_crud
from app.crud import user_admin as user_crud
from app.services.services_erp.inventory_service import inventory_filters


def csv_response(filename: str, fields: list[str], rows: list[dict]) -> Response:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def export_inventory_csv(db, q=None, color=None, size=None, low_stock=None, threshold: int = 5):
    filters = inventory_filters(q, color, size, low_stock, threshold)
    docs = await inventory_crud.list_inventory_items(db, filters, 0, 10000)
    rows = [
        {
            "product_id": str(doc["_id"]),
            "product_name": doc.get("full_name") or doc.get("name"),
            "sku": doc.get("sku"),
            "color": doc.get("color"),
            "size": doc.get("size"),
            "stock_on_hand": doc.get("stock_on_hand", 0),
            "stock_reserved": doc.get("stock_reserved", 0),
            "stock_available": doc.get("stock_available", 0),
            "in_stock": doc.get("in_stock", True),
        }
        for doc in docs
    ]
    return csv_response(
        "inventory.csv",
        ["product_id", "product_name", "sku", "color", "size", "stock_on_hand", "stock_reserved", "stock_available", "in_stock"],
        rows,
    )


async def export_orders_csv(db, filters: dict):
    docs = await order_crud.list_orders(db, filters, 0, 10000, ("created_at", -1))
    rows = [
        {
            "id": doc.get("id"),
            "created_at": doc.get("created_at"),
            "user_email": doc.get("user_email"),
            "status": doc.get("status"),
            "order_status": doc.get("order_status", doc.get("status")),
            "payment_status": doc.get("payment_status"),
            "fulfillment_status": doc.get("fulfillment_status"),
            "city": (doc.get("shipping") or {}).get("city"),
            "country": (doc.get("shipping") or {}).get("country"),
            "subtotal": doc.get("subtotal"),
            "discount_value": doc.get("discount_value"),
            "shipping_amount": doc.get("shipping_amount"),
            "total_amount": doc.get("total_amount"),
            "promo_code": doc.get("promo_code"),
        }
        for doc in docs
    ]
    return csv_response("orders.csv", list(rows[0].keys()) if rows else ["id"], rows)


async def export_clients_csv(db):
    docs = await user_crud.list_users(db, {}, 0, 10000, ("created_at", -1))
    fields = ["id", "email", "full_name", "is_active", "loyalty_points_balance", "created_at"]
    return csv_response("clients.csv", fields, docs)
