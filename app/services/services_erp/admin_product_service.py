from bson import ObjectId
from fastapi import HTTPException, status

from app.crud import product as product_crud
from app.services.services_store.product_service import product_to_out


def validate_product_id(product_id: str) -> None:
    try:
        ObjectId(product_id)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID invalide")


async def create_product(db, product):
    created = await product_crud.create_product(db, product)
    return product_to_out(created)


async def update_product(db, product_id: str, product):
    validate_product_id(product_id)
    existing = await product_crud.get_product(db, product_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouve")
    updated = await product_crud.update_product(db, product_id, product)
    if not updated:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Echec lors de la mise a jour")
    return product_to_out(updated)


async def delete_product(db, product_id: str) -> None:
    validate_product_id(product_id)
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouve")
    await product_crud.delete_product(db, product_id)
