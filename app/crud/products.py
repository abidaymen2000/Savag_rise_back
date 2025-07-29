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
    db, product_oid: ObjectId, color: str, size: str, qty: int
):
    """
    Décrémente le stock du variant (color,size) de qty unités,
    seulement si le stock courant >= qty.
    """
    res = await db["products"].update_one(
        {
            "_id": product_oid,
            "variants.color": color,
            "variants.size": size,
            # on vérifie qu'on a assez de stock
            "variants.stock": {"$gte": qty},
        },
        {
            # $inc négatif pour décrémenter
            "$inc": {"variants.$.stock": -qty}
        },
    )
    if res.modified_count == 0:
        # soit le variant est absent, soit stock insufisant
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Variant {color}/{size} introuvable ou stock < {qty}"
        )
    return