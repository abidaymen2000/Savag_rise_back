from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db import get_db
from app.schemas.pack import PackOut
from app.utils.pack_service import PACKS_COLLECTION, is_pack_public, pack_out, validate_object_id

router = APIRouter(prefix="/packs", tags=["packs"])


@router.get("", response_model=List[PackOut])
async def list_store_packs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    docs = await db[PACKS_COLLECTION].find({"status": "active"}).sort("order", 1).skip(skip).limit(limit).to_list(length=limit)
    return [await pack_out(db, doc) for doc in docs if is_pack_public(doc)]


@router.get("/{pack_id}", response_model=PackOut)
async def get_store_pack(pack_id: str, db=Depends(get_db)):
    oid = validate_object_id(pack_id, "Pack ID")
    doc = await db[PACKS_COLLECTION].find_one({"_id": oid})
    if not doc or not is_pack_public(doc):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pack introuvable")
    return await pack_out(db, doc)
