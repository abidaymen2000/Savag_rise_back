from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.pagination import PaginatedResponse, pagination_params, PaginationParams
from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.pack import PackCreate, PackOut, PackStatus, PackUpdate
from app.services.services_store import pack_service

router = APIRouter(prefix="/admin/packs", tags=["admin-packs"])


@router.get("", response_model=List[PackOut])
async def admin_list_packs(
    _admin=Depends(require_permission("packs")),
    db=Depends(get_db),
    status_filter: Optional[PackStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await pack_service.admin_list_packs(db, status_filter, skip, limit)


@router.get("/page", response_model=PaginatedResponse[PackOut])
async def admin_list_packs_page(
    _admin=Depends(require_permission("packs")),
    db=Depends(get_db),
    pagination: PaginationParams = Depends(pagination_params),
    status_filter: Optional[PackStatus] = Query(None, alias="status"),
):
    return await pack_service.admin_list_packs_page(db, pagination, status_filter)


@router.post("", response_model=PackOut, status_code=201)
async def admin_create_pack(
    payload: PackCreate,
    _admin=Depends(require_permission("packs")),
    db=Depends(get_db),
):
    return await pack_service.admin_create_pack(db, payload)


@router.get("/{pack_id}", response_model=PackOut)
async def admin_get_pack(pack_id: str, _admin=Depends(require_permission("packs")), db=Depends(get_db)):
    return await pack_service.admin_get_pack(db, pack_id)


@router.put("/{pack_id}", response_model=PackOut)
async def admin_update_pack(
    pack_id: str,
    payload: PackUpdate,
    _admin=Depends(require_permission("packs")),
    db=Depends(get_db),
):
    return await pack_service.admin_update_pack(db, pack_id, payload)


@router.delete("/{pack_id}", status_code=204)
async def admin_delete_pack(pack_id: str, _admin=Depends(require_permission("packs")), db=Depends(get_db)):
    await pack_service.admin_delete_pack(db, pack_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
