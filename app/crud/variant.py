# app/crud/variant.py

from typing import Any, Dict, List
from bson import ObjectId
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder

# 1) Création d'une variante couleur avec sa liste de tailles
async def add_variant(db, product_id: str, variant: Dict[str, Any]) -> Dict[str, Any]:
    pid = ObjectId(product_id)
    await db["products"].update_one(
        {"_id": pid},
        {"$push": {"variants": variant}}
    )
    return variant

# 2) Récupère toutes les variantes d'un produit
async def get_variants(db, product_id: str) -> List[Dict[str, Any]]:
    pid = ObjectId(product_id)
    prod = await db["products"].find_one(
        {"_id": pid},
        {"variants": 1}
    )
    if not prod:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouvé")
    return prod.get("variants", [])

# 3) Met à jour le stock d'une taille d'une couleur
async def update_variant_stock(
    db, product_id: str, color: str, size: str, new_stock: int
) -> int:
    pid = ObjectId(product_id)
    res = await db["products"].update_one(
        {
            "_id": pid,
            "variants.color": color
        },
        {
            "$set": {
                "variants.$.sizes.$[s].stock": new_stock
            }
        },
        array_filters=[{"s.size": size}]
    )
    return res.modified_count

# 4) Décrémente le stock d'une taille d'une couleur (pour les commandes)
async def decrement_variant_stock(
    db, product_id: str, color: str, size: str, qty: int
) -> bool:
    pid = ObjectId(product_id)
    res = await db["products"].update_one(
        {
            "_id": pid,
            "variants": {
                "$elemMatch": {
                    "color": color,
                    "sizes": {
                        "$elemMatch": {
                            "size": size,
                            "stock": {"$gte": qty}
                        }
                    }
                }
            }
        },
        {"$inc": {"variants.$.sizes.$[s].stock": -qty}},
        array_filters=[{"s.size": size}]
    )
    if res.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de commander {qty}× {color}/{size} : variante introuvable ou stock insuffisant"
        )
    return True

# 5) Ajoute une image (url, alt, etc.) à la galerie de la couleur
async def add_image_to_variant(
    db, product_id: str, color: str, image_dict: Dict[str, Any]
) -> Dict[str, Any]:
    pid = ObjectId(product_id)
    img_oid = ObjectId()
    payload = jsonable_encoder(image_dict)
    image_doc = {"_id": img_oid, **payload}

    res = await db["products"].update_one(
        {"_id": pid, "variants.color": color},
        {"$push": {"variants.$.images": image_doc}}
    )
    if res.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produit ou variante {color} introuvable"
        )
    return {"id": str(img_oid), **payload}

# 6) Retire une image de la galerie d'une couleur
async def remove_image_from_variant(
    db, product_id: str, color: str, image_id: str
) -> bool:
    pid = ObjectId(product_id)
    img_oid = ObjectId(image_id)
    res = await db["products"].update_one(
        {"_id": pid, "variants.color": color},
        {"$pull": {"variants.$.images": {"_id": img_oid}}}
    )
    if res.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image introuvable"
        )
    return True
