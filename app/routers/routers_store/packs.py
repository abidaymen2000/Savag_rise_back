from typing import List

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.schemas.pack import PackOut
from app.services.services_store import pack_service

router = APIRouter(prefix="/packs", tags=["packs"])


@router.get("", response_model=List[PackOut])
async def list_store_packs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    return await pack_service.list_public_packs(db, skip, limit)


@router.get("/{pack_id}", response_model=PackOut)
async def get_store_pack(pack_id: str, db=Depends(get_db)):
    return await pack_service.get_public_pack(db, pack_id)
