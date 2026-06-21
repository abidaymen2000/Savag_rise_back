from fastapi import HTTPException

from app.crud import category as category_crud
from app.crud.product import add_category_to_product
from app.services.services_store.category_service import category_to_out, list_categories_page
from app.services.services_store.product_service import product_to_out


async def create_category(db, payload):
    category = await category_crud.create_category(db, payload.model_dump())
    return category_to_out(category)


async def update_category(db, category_id: str, payload):
    existing = await category_crud.get_category(db, category_id)
    if not existing:
        raise HTTPException(404, "Categorie non trouvee")
    category = await category_crud.update_category(db, category_id, payload.model_dump(exclude_unset=True))
    return category_to_out(category)


async def delete_category(db, category_id: str) -> None:
    existing = await category_crud.get_category(db, category_id)
    if not existing:
        raise HTTPException(404, "Categorie non trouvee")
    await category_crud.delete_category(db, category_id)


async def add_product_to_category(db, category_id: str, product_id: str):
    category = await category_crud.get_category(db, category_id)
    if not category:
        raise HTTPException(404, "Categorie non trouvee")

    updated = await add_category_to_product(db, product_id, category["name"])
    if not updated:
        raise HTTPException(404, "Produit non trouve")
    return product_to_out(updated)
