import asyncio
import json
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


def read_env_value(name: str) -> str:
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"Variable {name} introuvable")


async def main():
    client = AsyncIOMotorClient(read_env_value("MONGODB_URL"))
    db = client[read_env_value("MONGODB_DB_NAME")]
    report = {
        "negative_on_hand": 0,
        "negative_reserved": 0,
        "reserved_gt_on_hand": 0,
        "active_orders_without_allocations": 0,
        "cancelled_orders_with_reserved_fulfillment": 0,
    }

    async for product in db["products"].find({}, {"variants": 1}):
        for variant in product.get("variants", []):
            for size in variant.get("sizes", []):
                on_hand = int(size.get("stock_on_hand", size.get("stock", 0)) or 0)
                reserved = int(size.get("stock_reserved", 0) or 0)
                if on_hand < 0:
                    report["negative_on_hand"] += 1
                if reserved < 0:
                    report["negative_reserved"] += 1
                if reserved > on_hand:
                    report["reserved_gt_on_hand"] += 1

    async for order in db["orders"].find({}, {"status": 1, "inventory_allocations": 1, "fulfillment_status": 1}):
        status_value = order.get("status")
        allocations = order.get("inventory_allocations", [])
        if status_value in {"pending", "confirmed", "preparing", "shipped", "delivered"} and not allocations:
            report["active_orders_without_allocations"] += 1
        if status_value == "cancelled" and order.get("fulfillment_status") == "reserved":
            report["cancelled_orders_with_reserved_fulfillment"] += 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
