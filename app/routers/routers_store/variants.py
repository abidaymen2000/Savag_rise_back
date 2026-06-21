from typing import List

from fastapi import APIRouter, Depends, Path

from app.db import get_db
from app.schemas.variant import VariantOut
from app.services.services_store import variant_service


router = APIRouter(prefix="/products/{product_id}/variants", tags=["variants"])


@router.get("/", response_model=List[VariantOut])
async def list_variants(product_id: str = Path(...), db=Depends(get_db)):
    return await variant_service.list_variants(db, product_id)
