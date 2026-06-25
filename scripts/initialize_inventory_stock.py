import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from bson import ObjectId


def read_env_value(name: str) -> str:
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"Variable {name} introuvable")


async def main():
    parser = argparse.ArgumentParser(description="Initialisation explicite du stock physique")
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--color", required=True)
    parser.add_argument("--size", required=True)
    parser.add_argument("--stock-on-hand", required=True, type=int)
    parser.add_argument("--actor-id", default="system")
    parser.add_argument("--actor-type", default="admin")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    operation_key = f"initial-stock:{args.product_id}:{args.color}:{args.size}:{args.stock_on_hand}"
    preview = {
        "mode": "apply" if args.apply else "dry-run",
        "product_id": args.product_id,
        "color": args.color,
        "size": args.size,
        "stock_on_hand": args.stock_on_hand,
        "stock_reserved": 0,
        "operation_key": operation_key,
    }
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    if not args.apply:
        return

    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(read_env_value("MONGODB_URL"))
    db = client[read_env_value("MONGODB_DB_NAME")]
    result = await db["products"].update_one(
        {"_id": ObjectId(args.product_id), "variants.color": args.color},
        {"$set": {"variants.$.sizes.$[s].stock_on_hand": args.stock_on_hand, "variants.$.sizes.$[s].stock_reserved": 0}},
        array_filters=[{"s.size": args.size}],
    )
    if result.modified_count == 0:
        raise SystemExit("Variante introuvable ou non modifiee")
    await db["inventory_movements"].update_one(
        {"operation_key": operation_key},
        {
            "$setOnInsert": {
                "variant_id": f"{args.product_id}:{args.color}:{args.size}",
                "product_id": args.product_id,
                "movement_type": "initial_stock",
                "on_hand_delta": args.stock_on_hand,
                "reserved_delta": 0,
                "on_hand_before": 0,
                "on_hand_after": args.stock_on_hand,
                "reserved_before": 0,
                "reserved_after": 0,
                "reason": "initial_stock_setup",
                "source": "inventory_initializer",
                "operation_key": operation_key,
                "actor_id": args.actor_id,
                "actor_type": args.actor_type,
                "metadata": {},
                "created_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
