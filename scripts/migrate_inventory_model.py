import argparse
import asyncio
import json
from pathlib import Path


def read_env_value(name: str) -> str:
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"Variable {name} introuvable dans .env")


def migrate_variant_sizes(product: dict) -> tuple[list[dict], dict]:
    changed = False
    total_before = 0
    total_after = 0
    migrated_sizes = 0
    variants = []
    for variant in product.get("variants", []) or []:
        variant_copy = dict(variant)
        sizes = []
        for size in variant.get("sizes", []) or []:
            stock_before = int(size.get("stock_on_hand", size.get("stock", 0)) or 0)
            reserved_before = int(size.get("stock_reserved", 0) or 0)
            total_before += int(size.get("stock", stock_before) or 0)
            migrated = {
                "size": size["size"],
                "stock_on_hand": stock_before,
                "stock_reserved": reserved_before,
            }
            if size.get("stock_on_hand") != migrated["stock_on_hand"] or size.get("stock_reserved", 0) != reserved_before or "stock" in size:
                changed = True
            sizes.append(migrated)
            total_after += migrated["stock_on_hand"]
            migrated_sizes += 1
        variant_copy["sizes"] = sizes
        variants.append(variant_copy)
    return variants, {
        "changed": changed,
        "total_before": total_before,
        "total_after": total_after,
        "migrated_sizes": migrated_sizes,
    }


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient

    parser = argparse.ArgumentParser(description="Migre variants.sizes.stock vers stock_on_hand/stock_reserved")
    parser.add_argument("--apply", action="store_true", help="Applique la migration")
    parser.add_argument("--drop-legacy-stock", action="store_true", help="Supprime le champ legacy stock dans les sizes")
    args = parser.parse_args()

    uri = read_env_value("MONGODB_URL")
    db_name = read_env_value("MONGODB_DB_NAME")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]
    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "products_scanned": 0,
        "products_to_update": 0,
        "sizes_scanned": 0,
        "total_stock_before": 0,
        "total_stock_after": 0,
        "warnings": [],
    }
    updates = []
    async for product in db["products"].find({}, {"variants": 1, "name": 1, "full_name": 1}):
        summary["products_scanned"] += 1
        variants, stats = migrate_variant_sizes(product)
        summary["sizes_scanned"] += stats["migrated_sizes"]
        summary["total_stock_before"] += stats["total_before"]
        summary["total_stock_after"] += stats["total_after"]
        if stats["changed"]:
            summary["products_to_update"] += 1
            updates.append({
                "product_id": str(product["_id"]),
                "product_name": product.get("full_name") or product.get("name"),
                "variants": variants,
            })

    if summary["total_stock_before"] != summary["total_stock_after"]:
        summary["warnings"].append("Le total du stock physique differe entre avant et apres migration")

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.apply:
        for update in updates:
            await db["products"].update_one(
                {"_id": __import__("bson").ObjectId(update["product_id"])},
                {"$set": {"variants": update["variants"]}},
            )
        if args.drop_legacy_stock:
            print("Suppression du champ legacy stock non implemente automatiquement. A executer seulement apres validation finale.")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
