from fastapi import HTTPException

from app.core.pagination import build_page
from app.crud import category as category_crud
from app.schemas.category import CategoryOut
from app.services.services_store.product_service import product_to_out


def category_to_out(category: dict) -> CategoryOut:
    return CategoryOut(
        id=str(category["_id"]),
        name=category["name"],
        description=category.get("description"),
        created_at=category["created_at"],
        updated_at=category["updated_at"],
    )


async def list_categories(db) -> list[CategoryOut]:
    return [category_to_out(category) for category in await category_crud.list_categories(db)]


async def list_categories_page(db, pagination, q: str | None):
    filters = {}
    if q:
        filters["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    total = await category_crud.count_categories(db, filters)
    docs = await category_crud.list_categories_page(db, filters, pagination.skip, pagination.page_size)
    return build_page(
        items=[category_to_out(category) for category in docs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        sort={"by": "created_at", "dir": "desc"},
        filters={"q": q},
    )


async def get_category(db, category_id: str) -> CategoryOut:
    category = await category_crud.get_category(db, category_id)
    if not category:
        raise HTTPException(404, "Categorie non trouvee")
    return category_to_out(category)


async def list_products_by_category(db, category_name: str, skip: int, limit: int):
    docs = await category_crud.list_products_by_category(db, category_name, skip, limit)
    return [product_to_out(doc) for doc in docs]
