import argparse
import asyncio
import json
from pathlib import Path


RESET_CONFIRMATION = "RESET SAVAGE RISE DATABASE"
BUSINESS_COLLECTIONS = [
    "orders",
    "order_status_history",
    "inventory_movements",
    "outbox_events",
    "loyalty_transactions",
    "analytics_events",
]


def read_env_value(name: str) -> str:
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"Variable {name} introuvable")


def mask_uri(uri: str) -> str:
    if "@" not in uri:
        return uri
    prefix, suffix = uri.split("@", 1)
    if "://" in prefix:
        scheme, creds = prefix.split("://", 1)
        return f"{scheme}://***:***@{suffix}"
    return f"***:***@{suffix}"


def build_reset_plan(mode: str) -> dict:
    if mode == "business":
        return {
            "collections_to_drop": BUSINESS_COLLECTIONS,
            "collections_to_keep": ["products", "packs", "users", "admins", "cms_settings", "cms_pages", "shipping_rates", "promocodes"],
            "post_actions": ["reset stock_reserved to 0 on every variant size"],
        }
    return {
        "collections_to_drop": "ALL_APPLICATION_COLLECTIONS",
        "collections_to_keep": [],
        "post_actions": [],
    }


async def main():
    parser = argparse.ArgumentParser(description="Reset securise de la base Savage Rise")
    parser.add_argument("--mode", choices=["business", "full"], default="business")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

    uri = read_env_value("MONGODB_URL")
    db_name = read_env_value("MONGODB_DB_NAME")
    plan = build_reset_plan(args.mode)
    output = {
        "mode": "apply" if args.apply else "dry-run",
        "reset_scope": args.mode,
        "database": db_name,
        "uri": mask_uri(uri),
        "plan": plan,
        "safe_to_execute": bool(args.apply and args.confirm == RESET_CONFIRMATION),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    if not args.apply:
        return
    if args.confirm != RESET_CONFIRMATION:
        raise SystemExit("Confirmation invalide. Operation abandonnee.")

    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(uri)
    db = client[db_name]
    if args.mode == "business":
        for collection in BUSINESS_COLLECTIONS:
            await db[collection].delete_many({})
        await db["products"].update_many({}, {"$set": {"variants.$[].sizes.$[].stock_reserved": 0}})
    else:
        existing = await db.list_collection_names()
        for collection in existing:
            await db[collection].drop()
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
