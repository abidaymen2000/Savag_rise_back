# app/routers/categories.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from bson import ObjectId
from app.crud.product import add_category_to_product
from app.dependencies import get_db
from app.schemas.category import (
    CategoryCreate, CategoryUpdate, CategoryOut
)
from app.schemas.product import ProductOut
from app.crud.category import (
    list_categories, get_category,
    create_category, update_category, delete_category
)

router = APIRouter(prefix="/categories", tags=["Categories"])

# --- CRUD categories ---

@router.get("/", response_model=List[CategoryOut])
async def read_categories(db=Depends(get_db)):
    cats = await list_categories(db)
    return [
        CategoryOut(
            id=str(c["_id"]),
            name=c["name"],
            description=c.get("description"),
            created_at=c["created_at"],
            updated_at=c["updated_at"]
        ) for c in cats
    ]

@router.get("/{category_id}", response_model=CategoryOut)
async def read_category(category_id: str, db=Depends(get_db)):
    cat = await get_category(db, category_id)
    if not cat:
        raise HTTPException(404, "Catégorie non trouvée")
    return CategoryOut(
        id=str(cat["_id"]),
        name=cat["name"],
        description=cat.get("description"),
        created_at=cat["created_at"],
        updated_at=cat["updated_at"]
    )

@router.post("/", response_model=CategoryOut, status_code=201)
async def create_new_category(payload: CategoryCreate, db=Depends(get_db)):
    cat = await create_category(db, payload.dict())
    return CategoryOut(
        id=str(cat["_id"]),
        name=cat["name"],
        description=cat.get("description"),
        created_at=cat["created_at"],
        updated_at=cat["updated_at"]
    )

@router.put("/{category_id}", response_model=CategoryOut)
async def modify_category(category_id: str, payload: CategoryUpdate, db=Depends(get_db)):
    existing = await get_category(db, category_id)
    if not existing:
        raise HTTPException(404, "Catégorie non trouvée")
    cat = await update_category(db, category_id, payload.dict(exclude_unset=True))
    return CategoryOut(
        id=str(cat["_id"]),
        name=cat["name"],
        description=cat.get("description"),
        created_at=cat["created_at"],
        updated_at=cat["updated_at"]
    )

@router.delete("/{category_id}", status_code=204)
async def remove_category(category_id: str, db=Depends(get_db)):
    existing = await get_category(db, category_id)
    if not existing:
        raise HTTPException(404, "Catégorie non trouvée")
    await delete_category(db, category_id)

# --- Produits par catégorie (lecture) ---

@router.get("/{category_name}/products", response_model=List[ProductOut])
async def products_by_category(
    category_name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(get_db)
):
    cursor = db["products"].find({"categories": category_name}).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [
        ProductOut(**{**d, "id": str(d["_id"])})
        for d in docs
    ]

@router.post(
    "/{category_id}/products/{product_id}",
    response_model=ProductOut,
    summary="Ajoute un produit existant à une catégorie existante"
)
async def add_product_to_category(
    category_id: str,
    product_id: str,
    db=Depends(get_db)
):
    # 1) Vérifier que la catégorie existe
    cat = await get_category(db, category_id)
    if not cat:
        raise HTTPException(404, "Catégorie non trouvée")

    # 2) Injecter cat["name"] dans le produit
    updated = await add_category_to_product(db, product_id, cat["name"])
    if not updated:
        raise HTTPException(404, "Produit non trouvé")

    # 3) Retourner le produit mis à jour (convertir l’ObjectId en str)
    updated["id"] = str(updated["_id"])
    return ProductOut(**updated)