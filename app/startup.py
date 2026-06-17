# app/startup.py
import logging
from .config import settings
from .db import client

logger = logging.getLogger("startup")

async def init_mongo():
    """
    Vérifie et crée les collections et index Mongo si nécessaire.
    """
    db = client[settings.MONGODB_DB_NAME]
    existing = await db.list_collection_names()

    # --- USERS ---
    if "users" not in existing:
        await db.create_collection("users")
    # email unique
    await db["users"].create_index("email", unique=True, background=True)
    await db["users"].create_index("created_at", background=True)
    await db["users"].create_index("loyalty_points_balance", background=True)
    async for user in db["users"].find({"created_at": {"$exists": False}}, {"_id": 1}):
        created_at = user["_id"].generation_time.replace(tzinfo=None)
        await db["users"].update_one(
            {"_id": user["_id"]},
            {"$set": {"created_at": created_at, "updated_at": created_at}},
        )

    # --- PRODUCTS ---
    if "products" not in existing:
        await db.create_collection("products")

    # 1) Index texte pour le plein‐texte sur name, full_name et description
    await db["products"].create_index(
        [("name", "text"), ("full_name", "text"), ("description", "text")],
        name="product_text_idx",
        default_language="french",
        background=True,
    )

    # 2) Index “facettes” pour accélérer les filtres
    #    – prix
    await db["products"].create_index("price", background=True)
    await db["products"].create_index("gender", background=True)
    #    – variants.color et variants.size (tableau “variants”)
    await db["products"].create_index("variants.color", background=True)
    await db["products"].create_index("variants.size",  background=True)

    if "packs" not in existing:
        await db.create_collection("packs")

    await db["packs"].create_index([("status", 1), ("order", 1)], background=True)
    await db["packs"].create_index("product_ids", background=True)
    await db["packs"].create_index([("starts_at", 1), ("ends_at", 1)], background=True)

    # --- ORDERS & AUTRES (si besoin) ---
    if "orders" not in existing:
        await db.create_collection("orders")
        # index sur user_id pour retrouver rapidement les commandes d’un user
    # etc.
    await db["orders"].create_index("user_id", background=True)
    await db["orders"].create_index("loyalty_points_awarded", background=True)

    if "reviews" not in existing:
        await db.create_collection("reviews")
        # indexer sur product_id et user_id pour accélérer recherches et filtres
        await db["reviews"].create_index("product_id")
        await db["reviews"].create_index("user_id")
    await db["reviews"].create_index([("status", 1), ("created_at", -1)], background=True)
    await db["reviews"].create_index([("product_id", 1), ("status", 1), ("created_at", -1)], background=True)


    if "wishlist" not in existing:
        await db.create_collection("wishlist")
        # indexer sur user_id pour retrouver rapidement la liste de chaque utilisateur
        await db["wishlist"].create_index("user_id")
        # index unique sur (user_id, product_id) pour empêcher les doublons
        await db["wishlist"].create_index(
            [("user_id", 1), ("product_id", 1)],
            unique=True
        )


    if "promocodes" not in existing:
        await db.create_collection("promocodes")

    # index unique sur le code
    await db["promocodes"].create_index("code", unique=True)        

    if "shipping_rates" not in existing:
        await db.create_collection("shipping_rates")

    await db["shipping_rates"].create_index("is_active", background=True)
    await db["shipping_rates"].create_index([("country", 1), ("city", 1)], background=True)

    if await db["shipping_rates"].count_documents({}) == 0:
        from datetime import datetime
        now = datetime.utcnow()
        await db["shipping_rates"].insert_one({
            "name": "Livraison standard",
            "country": "Tunisia",
            "city": None,
            "price": 7,
            "free_shipping_threshold": 300,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
    
    
    if "admins" not in existing:
        await db.create_collection("admins")
        await db["admins"].create_index("email", unique=True)
    await db["admins"].create_index("is_active", background=True)
    await db["admins"].update_one(
        {"email": {"$regex": "^Savage\\.rise\\.tn@gmail\\.com$", "$options": "i"}},
        {"$set": {"is_superadmin": True, "permissions": [], "is_active": True}},
    )

    if "cms_pages" not in existing:
        await db.create_collection("cms_pages")

    await db["cms_pages"].create_index("key", unique=True, background=True)
    await db["cms_pages"].create_index([("is_active", 1), ("order", 1)], background=True)
    from app.crud.admin import ensure_default_cms_pages
    await ensure_default_cms_pages()

    if "cms_settings" not in existing:
        await db.create_collection("cms_settings")
    await db["cms_settings"].create_index([("value.launch_at", 1), ("notification_sent_at", 1)], background=True)
    await db["users"].create_index([("is_active", 1), ("email", 1)], background=True)
    if "drop_notification_subscribers" not in existing:
        await db.create_collection("drop_notification_subscribers")
    await db["drop_notification_subscribers"].create_index(
        [("drop_key", 1), ("user_id", 1)],
        unique=True,
        background=True,
    )
    await db["drop_notification_subscribers"].create_index("drop_key", background=True)

    if "loyalty_transactions" not in existing:
        await db.create_collection("loyalty_transactions")

    await db["loyalty_transactions"].create_index([("user_id", 1), ("created_at", -1)], background=True)
    await db["loyalty_transactions"].create_index("order_id", background=True)
    await db["loyalty_transactions"].create_index([("type", 1), ("created_at", -1)], background=True)

    if "vlog_chapters" not in existing:
        await db.create_collection("vlog_chapters")

    await db["vlog_chapters"].create_index("slug", unique=True, background=True)
    await db["vlog_chapters"].create_index([("status", 1), ("order", 1)], background=True)

    if "vlog_episodes" not in existing:
        await db.create_collection("vlog_episodes")

    await db["vlog_episodes"].create_index([("chapter_id", 1), ("order", 1)], background=True)
    await db["vlog_episodes"].create_index([("status", 1), ("release_date", 1)], background=True)
    await db["vlog_episodes"].create_index("view_count", background=True)

    if "vlog_media" not in existing:
        await db.create_collection("vlog_media")

    await db["vlog_media"].create_index("file_id", background=True)
    await db["vlog_media"].create_index([("media_type", 1), ("_id", -1)], background=True)

    if "vlog_episode_likes" not in existing:
        await db.create_collection("vlog_episode_likes")

    await db["vlog_episode_likes"].create_index(
        [("episode_id", 1), ("user_id", 1)],
        unique=True,
        background=True,
    )
    await db["vlog_episode_likes"].create_index("user_id", background=True)

    if "vlog_comments" not in existing:
        await db.create_collection("vlog_comments")

    await db["vlog_comments"].create_index([("episode_id", 1), ("status", 1), ("created_at", -1)], background=True)
    await db["vlog_comments"].create_index([("user_id", 1), ("created_at", -1)], background=True)
    await db["vlog_comments"].create_index([("status", 1), ("created_at", -1)], background=True)
