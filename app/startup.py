from .config import settings
from .db import client

async def init_mongo():
    """
    Vérifie et crée les collections Mongo si nécessaire.
    """
    db = client[settings.MONGODB_DB_NAME]
    existing = await db.list_collection_names()

    if "users" not in existing:
        await db.create_collection("users")
        await db["users"].create_index("email", unique=True)

    if "products" not in existing:
        await db.create_collection("products")
        # tu peux ici ajouter d'autres indexes par ex. images.url

    # … éventuels autres setups (orders, carts…)
