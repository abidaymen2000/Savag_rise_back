from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from .. import crud, schemas
from ..db import get_db

router = APIRouter(prefix="/products", tags=["products"])

@router.post("/", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(product: schemas.ProductCreate, db=Depends(get_db)):
    created = await crud.create_product(db, product)
    return {"id": str(created["_id"]), **product.dict(), "in_stock": created["in_stock"]}

@router.get("/", response_model=List[schemas.ProductOut])
async def list_products(skip: int = 0, limit: int = 10, db=Depends(get_db)):
    prods = await crud.get_products(db, skip, limit)
    return [{"id": str(p["_id"]), **p} for p in prods]

@router.get("/{product_id}", response_model=schemas.ProductOut)
async def read_product(product_id: str, db=Depends(get_db)):
    prod = await crud.get_product(db, product_id)
    if not prod:
        raise HTTPException(404, "Produit non trouvé")
    return {"id": str(prod["_id"]), **prod}
