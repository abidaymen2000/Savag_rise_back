from typing import List

from bson import ObjectId
from fastapi import HTTPException, status

from app.crud import variant as variant_crud
from app.schemas.variant import VariantOut


def parse_product_id(product_id: str) -> str:
    try:
        ObjectId(product_id)
        return product_id
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID produit invalide")


async def list_variants(db, product_id: str) -> List[VariantOut]:
    raw_variants = await variant_crud.get_variants(db, parse_product_id(product_id))
    remapped = []
    for variant in raw_variants:
        item = dict(variant)
        item["images"] = [
            {
                "id": str(image["_id"]),
                **{key: value for key, value in image.items() if key != "_id"},
            }
            for image in item.get("images", [])
        ]
        remapped.append(VariantOut(**item))
    return remapped
