# app/crud/variant.py
from typing import Any, Dict, List

from bson import ObjectId
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder


async def add_variant(db, product_id: str, variant: Dict[str, Any]) -> Dict[str, Any]:
    pid = ObjectId(product_id)
    await db["products"].update_one(
        {"_id": pid},
        {"$push": {"variants": variant}},
    )
    return variant


async def find_variants(db, product_id: str):
    product = await db["products"].find_one(
        {"_id": ObjectId(product_id)},
        {"variants": 1},
    )
    return None if not product else product.get("variants", [])


async def get_variants(db, product_id: str) -> List[Dict[str, Any]]:
    pid = ObjectId(product_id)
    prod = await db["products"].find_one(
        {"_id": pid},
        {"variants": 1},
    )
    if not prod:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouve")
    return prod.get("variants", [])


async def rename_variant_color(db, product_id: str, current_color: str, new_color: str) -> int:
    result = await db["products"].update_one(
        {"_id": ObjectId(product_id), "variants.color": current_color},
        {"$set": {"variants.$.color": new_color}},
    )
    return result.modified_count


async def add_size_to_variant(db, product_id: str, color: str, size_data: Dict[str, Any]) -> int:
    result = await db["products"].update_one(
        {
            "_id": ObjectId(product_id),
            "variants": {
                "$elemMatch": {
                    "color": color,
                    "sizes": {"$not": {"$elemMatch": {"size": size_data["size"]}}},
                }
            },
        },
        {"$push": {"variants.$.sizes": size_data}},
    )
    return result.modified_count


async def update_variant_stock(db, product_id: str, color: str, size: str, new_stock_on_hand: int) -> int:
    pid = ObjectId(product_id)
    res = await db["products"].update_one(
        {"_id": pid, "variants.color": color},
        {
            "$set": {
                "variants.$.sizes.$[s].stock_on_hand": new_stock_on_hand,
            }
        },
        array_filters=[{"s.size": size}],
    )
    return res.modified_count


async def add_image_to_variant(db, product_id: str, color: str, image_dict: Dict[str, Any]) -> Dict[str, Any]:
    pid = ObjectId(product_id)
    img_oid = ObjectId()
    payload = jsonable_encoder(image_dict)
    image_doc = {"_id": img_oid, **payload}

    res = await db["products"].update_one(
        {"_id": pid, "variants.color": color},
        {"$push": {"variants.$.images": image_doc}},
    )
    if res.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produit ou variante {color} introuvable",
        )
    return {"id": str(img_oid), **payload}


async def remove_image_from_variant(db, product_id: str, color: str, image_id: str) -> bool:
    pid = ObjectId(product_id)
    img_oid = ObjectId(image_id)
    res = await db["products"].update_one(
        {"_id": pid, "variants.color": color},
        {"$pull": {"variants.$.images": {"_id": img_oid}}},
    )
    if res.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image introuvable",
        )
    return True
