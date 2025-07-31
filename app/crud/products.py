# app/crud/product.py
from bson import ObjectId
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from ..schemas.product import ProductCreate, ProductUpdate

async def get_product(db, product_id: str):
    return await db["products"].find_one({"_id": ObjectId(product_id)})

async def get_products(db, skip: int = 0, limit: int = 10):
    cursor = db["products"].find().skip(skip).limit(limit)
    return await cursor.to_list(length=limit)

async def create_product(db, product: ProductCreate):
    doc = jsonable_encoder(product)
    res = await db["products"].insert_one(doc)
    return await db["products"].find_one({"_id": res.inserted_id})

async def update_product(db, product_id: str, data: ProductUpdate):
    oid = ObjectId(product_id)
    upd = data.dict(exclude_unset=True)
    if upd:
        await db["products"].update_one({"_id": oid}, {"$set": upd})
    return await db["products"].find_one({"_id": oid})

async def delete_product(db, product_id: str):
    oid = ObjectId(product_id)
    await db["products"].delete_one({"_id": oid})

async def add_variant(db, product_id: ObjectId, variant: dict):
    """Ajoute un nouveau variant au produit"""
    await db["products"].update_one(
        {"_id": product_id},
        {"$push": {"variants": variant}}
    )
    return variant

async def update_variant_stock(
    db, product_id: ObjectId, color: str, size: str, new_stock: int
):
    """Met à jour le stock d’un variant donné."""
    res = await db["products"].update_one(
        {"_id": product_id, "variants.color": color, "variants.size": size},
        {"$set": {"variants.$.stock": new_stock}}
    )
    return res.modified_count

async def get_variants(db, product_id: ObjectId):
    prod = await db["products"].find_one({"_id": product_id}, {"variants": 1})
    return prod.get("variants", []) if prod else []

# app/crud/product.py

async def add_variant(db, product_id: ObjectId, variant: dict):
    """Ajoute un nouveau variant au produit"""
    await db["products"].update_one(
        {"_id": product_id},
        {"$push": {"variants": variant}}
    )
    return variant

async def update_variant_stock(
    db, product_id: ObjectId, color: str, size: str, new_stock: int
):
    """Met à jour le stock d’un variant donné."""
    res = await db["products"].update_one(
        {"_id": product_id, "variants.color": color, "variants.size": size},
        {"$set": {"variants.$.stock": new_stock}}
    )
    return res.modified_count

async def get_variants(db, product_id: ObjectId):
    prod = await db["products"].find_one({"_id": product_id}, {"variants": 1})
    return prod.get("variants", []) if prod else []

async def decrement_variant_stock(
    db, product_id: ObjectId, color: str, size: str, qty: int
):
    """
    Décrémente de qty le stock de la variante (color, size),
    seulement si la variante existe ET que son stock >= qty.
    En cas d’échec, lève une HTTPException 400.
    """
    res = await db["products"].update_one(
        {
            "_id": product_id,
            # On ne fait matcher qu’UNE entrée de variants qui 
            # doit simultanément correspondre à color, size et avoir assez de stock
            "variants": {
                "$elemMatch": {
                    "color": color,
                    "size": size,
                    "stock": { "$gte": qty },
                }
            },
        },
        {
            # On décrémente atomiquement le stock de l’élément matché
            "$inc": { "variants.$.stock": -qty }
        },
    )

    if res.modified_count == 0:
        # soit la variante n’existe pas, soit stock insuffisant
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Impossible de commander {qty}× {color}/{size} : "
                "variante introuvable ou stock insuffisant"
            )
        )
    return True