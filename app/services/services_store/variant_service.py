from typing import List

from bson import ObjectId
from fastapi import HTTPException, status

from app.crud import product as product_crud
from app.schemas.variant import VariantOut
from app.services.services_store.product_service import product_to_out


def parse_product_id(product_id: str) -> str:
    try:
        ObjectId(product_id)
        return product_id
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID produit invalide")


async def list_variants(db, product_id: str) -> List[VariantOut]:
    normalized_product_id = parse_product_id(product_id)
    product = await product_crud.get_product(db, normalized_product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produit non trouve")
    return product_to_out(product).variants
