# app/routers/variants.py
from fastapi import APIRouter, Depends, HTTPException, status, Path
from bson import ObjectId
from typing import List
from ..schemas.variant import VariantCreate, VariantOut
from ..db import get_db
from ..crud.products import add_variant, get_variants, update_variant_stock

router = APIRouter(prefix="/products/{product_id}/variants", tags=["variants"])

def parse_oid(pid: str) -> ObjectId:
    try:
        return ObjectId(pid)
    except:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID invalide")

@router.get("/", response_model=List[VariantOut])
async def list_variants(
    product_id: str = Path(...), db=Depends(get_db)
):
    oid = parse_oid(product_id)
    return await get_variants(db, oid)

@router.post(
    "/",
    response_model=VariantOut,
    status_code=status.HTTP_201_CREATED
)
async def create_variant(
    product_id: str,
    v: VariantCreate,
    db=Depends(get_db)
):
    oid = parse_oid(product_id)
    # Optionnel : vérifier qu’aucun variant identique n’existe déjà
    return await add_variant(db, oid, v.dict())

@router.patch(
    "/{color}/{size}/stock",
    status_code=status.HTTP_204_NO_CONTENT
)
async def change_stock(
    product_id: str,
    color: str,
    size: str,
    new_stock: int,
    db=Depends(get_db)
):
    oid = parse_oid(product_id)
    modified = await update_variant_stock(db, oid, color, size, new_stock)
    if not modified:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variant non trouvé")
    return
