# app/startup.py
import logging
from .config import settings
from .db import client
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger("startup")
# on force TLS, on donne le CA cert bundle fourni par certifi
client = AsyncIOMotorClient(
    settings.mongodb_url,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000  # 10s timeout max
)
db = client[settings.mongodb_db_name]

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
    #    – variants.color et variants.size (tableau “variants”)
    await db["products"].create_index("variants.color", background=True)
    await db["products"].create_index("variants.size",  background=True)

    # --- ORDERS & AUTRES (si besoin) ---
    if "orders" not in existing:
        await db.create_collection("orders")
        # index sur user_id pour retrouver rapidement les commandes d’un user
    # etc.

    if "reviews" not in existing:
        await db.create_collection("reviews")
        # indexer sur product_id et user_id pour accélérer recherches et filtres
        await db["reviews"].create_index("product_id")
        await db["reviews"].create_index("user_id")


    if "wishlist" not in existing:
        await db.create_collection("wishlist")
        # indexer sur user_id pour retrouver rapidement la liste de chaque utilisateur
        await db["wishlist"].create_index("user_id")
        # index unique sur (user_id, product_id) pour empêcher les doublons
        await db["wishlist"].create_index(
            [("user_id", 1), ("product_id", 1)],
            unique=True
        )