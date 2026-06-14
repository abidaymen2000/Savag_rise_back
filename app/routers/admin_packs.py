from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.db import get_db
from app.dependencies_admin import get_current_admin
from app.schemas.pack import PackCreate, PackOut, PackStatus, PackUpdate
from app.utils.pack_service import (
    PACKS_COLLECTION,
    normalize_pack_components,
    now_utc,
    pack_out,
    validate_object_id,
    validate_pack_components,
)

router = APIRouter(prefix="/admin/packs", tags=["admin-packs"])


@router.get("", response_model=List[PackOut])
async def admin_list_packs(
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
    status_filter: Optional[PackStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    filters = {}
    if status_filter:
        filters["status"] = status_filter
    docs = await db[PACKS_COLLECTION].find(filters).sort("order", 1).skip(skip).limit(limit).to_list(length=limit)
    return [await pack_out(db, doc) for doc in docs]


@router.post("", response_model=PackOut, status_code=201)
async def admin_create_pack(
    payload: PackCreate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    now = now_utc()
    data = normalize_pack_components(payload.model_dump())
    await validate_pack_components(db, data["components"])
    data["created_at"] = now
    data["updated_at"] = now
    res = await db[PACKS_COLLECTION].insert_one(data)
    created = await db[PACKS_COLLECTION].find_one({"_id": res.inserted_id})
    return await pack_out(db, created)


@router.get("/{pack_id}", response_model=PackOut)
async def admin_get_pack(pack_id: str, _admin=Depends(get_current_admin), db=Depends(get_db)):
    oid = validate_object_id(pack_id, "Pack ID")
    doc = await db[PACKS_COLLECTION].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pack introuvable")
    return await pack_out(db, doc)


@router.put("/{pack_id}", response_model=PackOut)
async def admin_update_pack(
    pack_id: str,
    payload: PackUpdate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    oid = validate_object_id(pack_id, "Pack ID")
    existing = await db[PACKS_COLLECTION].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pack introuvable")
    data = payload.model_dump(exclude_unset=True)
    if "components" in data or "product_ids" in data:
        base = {k: v for k, v in existing.items() if k != "_id"}
        base.update(data)
        base = normalize_pack_components(base)
        await validate_pack_components(db, base["components"])
        data["components"] = base["components"]
        data["product_ids"] = base["product_ids"]
    data["updated_at"] = now_utc()
    await db[PACKS_COLLECTION].update_one({"_id": oid}, {"$set": data})
    updated = await db[PACKS_COLLECTION].find_one({"_id": oid})
    return await pack_out(db, updated)


@router.delete("/{pack_id}", status_code=204)
async def admin_delete_pack(pack_id: str, _admin=Depends(get_current_admin), db=Depends(get_db)):
    oid = validate_object_id(pack_id, "Pack ID")
    existing = await db[PACKS_COLLECTION].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pack introuvable")
    await db[PACKS_COLLECTION].delete_one({"_id": oid})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
