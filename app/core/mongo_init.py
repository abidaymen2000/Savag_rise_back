import logging
from datetime import datetime
from typing import Any

from app.crud.admin import ensure_default_cms_pages


logger = logging.getLogger("mongo_init")


COLLECTION_INDEXES: dict[str, list[dict[str, Any]]] = {
    "users": [
        {"keys": "email", "options": {"unique": True, "background": True}},
        {"keys": "created_at", "options": {"background": True}},
        {"keys": "loyalty_points_balance", "options": {"background": True}},
        {"keys": [("is_active", 1), ("email", 1)], "options": {"background": True}},
    ],
    "products": [
        {
            "keys": [("name", "text"), ("full_name", "text"), ("description", "text")],
            "options": {"name": "product_text_idx", "default_language": "french", "background": True},
        },
        {"keys": "price", "options": {"background": True}},
        {"keys": "gender", "options": {"background": True}},
        {"keys": "variants.color", "options": {"background": True}},
        {"keys": "variants.size", "options": {"background": True}},
    ],
    "packs": [
        {"keys": [("status", 1), ("order", 1)], "options": {"background": True}},
        {"keys": "product_ids", "options": {"background": True}},
        {"keys": [("starts_at", 1), ("ends_at", 1)], "options": {"background": True}},
    ],
    "orders": [
        {"keys": "user_id", "options": {"background": True}},
        {"keys": "loyalty_points_awarded", "options": {"background": True}},
        {
            "keys": "idempotency_key",
            "options": {
                "unique": True,
                "background": True,
                "partialFilterExpression": {"idempotency_key": {"$type": "string"}},
            },
        },
        {"keys": [("status", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("payment_status", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("fulfillment_status", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("user_email", 1), ("created_at", -1)], "options": {"background": True}},
    ],
    "order_idempotency": [
        {"keys": "key", "options": {"unique": True, "background": True}},
        {"keys": [("status", 1), ("updated_at", -1)], "options": {"background": True}},
    ],
    "analytics_events": [
        {"keys": [("event_name", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("product_id", 1), ("event_name", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("source", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("utm_campaign", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("user_id", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("anonymous_id", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("session_id", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("event_category", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("device_type", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("page_path", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("action_target", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("utm_source", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("utm_medium", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("metadata.page_path", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("metadata.button_id", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("has_account", 1), ("created_at", -1)], "options": {"background": True}},
    ],
    "admin_notifications": [
        {"keys": [("created_at", -1)], "options": {"background": True}},
        {"keys": [("recipient_admin_id", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("category", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("priority", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": "read_by_admin_ids", "options": {"background": True}},
    ],
    "admin_audit_logs": [
        {"keys": [("created_at", -1)], "options": {"background": True}},
        {"keys": [("module", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("admin_id", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("entity_type", 1), ("entity_id", 1)], "options": {"background": True}},
    ],
    "inventory_movements": [
        {"keys": [("created_at", -1)], "options": {"background": True}},
        {"keys": [("product_id", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("color", 1), ("size", 1)], "options": {"background": True}},
        {"keys": "operation_key", "options": {"unique": True, "background": True}},
        {"keys": [("order_id", 1), ("created_at", -1)], "options": {"background": True}},
    ],
    "order_status_history": [
        {"keys": [("order_id", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("event_type", 1), ("created_at", -1)], "options": {"background": True}},
    ],
    "outbox_events": [
        {"keys": "operation_key", "options": {"unique": True, "background": True}},
        {"keys": [("status", 1), ("next_retry_at", 1)], "options": {"background": True}},
        {"keys": [("aggregate_type", 1), ("aggregate_id", 1)], "options": {"background": True}},
    ],
    "reviews": [
        {"keys": "product_id", "options": {"background": True}},
        {"keys": "user_id", "options": {"background": True}},
        {"keys": [("status", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("product_id", 1), ("status", 1), ("created_at", -1)], "options": {"background": True}},
    ],
    "wishlist": [
        {"keys": "user_id", "options": {"background": True}},
        {"keys": [("user_id", 1), ("product_id", 1)], "options": {"unique": True, "background": True}},
    ],
    "promocodes": [
        {"keys": "code", "options": {"unique": True, "background": True}},
    ],
    "shipping_rates": [
        {"keys": "is_active", "options": {"background": True}},
        {"keys": [("country", 1), ("city", 1)], "options": {"background": True}},
    ],
    "admins": [
        {"keys": "email", "options": {"unique": True, "background": True}},
        {"keys": "is_active", "options": {"background": True}},
    ],
    "cms_pages": [
        {"keys": "key", "options": {"unique": True, "background": True}},
        {"keys": [("is_active", 1), ("order", 1)], "options": {"background": True}},
    ],
    "cms_settings": [
        {"keys": [("value.launch_at", 1), ("notification_sent_at", 1)], "options": {"background": True}},
    ],
    "drop_notification_subscribers": [
        {"keys": [("drop_key", 1), ("user_id", 1)], "options": {"unique": True, "background": True}},
        {"keys": "drop_key", "options": {"background": True}},
    ],
    "loyalty_transactions": [
        {"keys": [("user_id", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": "order_id", "options": {"background": True}},
        {"keys": [("type", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": "operation_key", "options": {"unique": True, "sparse": True, "background": True}},
    ],
    "vlog_chapters": [
        {"keys": "slug", "options": {"unique": True, "background": True}},
        {"keys": [("status", 1), ("order", 1)], "options": {"background": True}},
    ],
    "vlog_episodes": [
        {"keys": [("chapter_id", 1), ("order", 1)], "options": {"background": True}},
        {"keys": [("status", 1), ("release_date", 1)], "options": {"background": True}},
        {"keys": "view_count", "options": {"background": True}},
    ],
    "vlog_media": [
        {"keys": "file_id", "options": {"background": True}},
        {"keys": [("media_type", 1), ("_id", -1)], "options": {"background": True}},
    ],
    "vlog_episode_likes": [
        {"keys": [("episode_id", 1), ("user_id", 1)], "options": {"unique": True, "background": True}},
        {"keys": "user_id", "options": {"background": True}},
    ],
    "vlog_comments": [
        {"keys": [("episode_id", 1), ("status", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("user_id", 1), ("created_at", -1)], "options": {"background": True}},
        {"keys": [("status", 1), ("created_at", -1)], "options": {"background": True}},
    ],
}


async def ensure_collection(db, existing_collections: set[str], collection_name: str) -> None:
    if collection_name not in existing_collections:
        await db.create_collection(collection_name)
        existing_collections.add(collection_name)


async def ensure_indexes(db, collection_name: str, index_specs: list[dict[str, Any]]) -> None:
    for spec in index_specs:
        await db[collection_name].create_index(spec["keys"], **spec["options"])


async def ensure_core_collections_and_indexes(db) -> None:
    existing_collections = set(await db.list_collection_names())
    for collection_name, index_specs in COLLECTION_INDEXES.items():
        await ensure_collection(db, existing_collections, collection_name)
        await ensure_indexes(db, collection_name, index_specs)


async def backfill_user_timestamps(db) -> None:
    async for user in db["users"].find({"created_at": {"$exists": False}}, {"_id": 1}):
        created_at = user["_id"].generation_time.replace(tzinfo=None)
        await db["users"].update_one(
            {"_id": user["_id"]},
            {"$set": {"created_at": created_at, "updated_at": created_at}},
        )


async def ensure_default_shipping_rate(db) -> None:
    if await db["shipping_rates"].count_documents({}) > 0:
        return
    now = datetime.utcnow()
    await db["shipping_rates"].insert_one(
        {
            "name": "Livraison standard",
            "country": "Tunisia",
            "city": None,
            "price": 7,
            "free_shipping_threshold": 300,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
    )


async def ensure_superadmin_defaults(db) -> None:
    await db["admins"].update_one(
        {"email": {"$regex": "^Savage\\.rise\\.tn@gmail\\.com$", "$options": "i"}},
        {"$set": {"is_superadmin": True, "permissions": [], "is_active": True}},
    )


async def init_mongo_database(db) -> None:
    logger.info("Initialisation MongoDB")
    await ensure_core_collections_and_indexes(db)
    await backfill_user_timestamps(db)
    await ensure_default_shipping_rate(db)
    await ensure_superadmin_defaults(db)
    await ensure_default_cms_pages()
