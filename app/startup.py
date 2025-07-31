# app/startup.py
from .config import settings
from .db import client

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
