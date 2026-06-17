from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.crud import admin as admin_crud
from app.dependencies_admin import admin_capabilities, admin_nav_items, get_current_admin, require_superadmin
from app.schemas.admin import CmsPageCreate, CmsPageUpdate

router = APIRouter(prefix="/admin/cms-pages", tags=["admin-cms-pages"])


@router.get("/sidebar", summary="Sidebar CMS de l'admin connecte")
async def current_admin_sidebar(current_admin=Depends(get_current_admin)):
    return {
        "items": await admin_nav_items(current_admin),
        "capabilities": await admin_capabilities(current_admin),
        "permissions": current_admin.permissions or [],
    }


@router.get("", summary="Lister les pages CMS")
async def list_admin_cms_pages(_super=Depends(require_superadmin)):
    return {
        "items": await admin_crud.list_cms_pages(include_inactive=True),
    }


@router.post("", status_code=201, summary="Creer une page CMS / permission")
async def create_admin_cms_page(
    payload: CmsPageCreate,
    _super=Depends(require_superadmin),
):
    data = payload.model_dump()
    if await admin_crud.get_cms_page_by_key(data["key"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "Permission CMS deja existante")
    try:
        return await admin_crud.create_cms_page(data)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Permission CMS deja existante")


@router.patch("/{page_id}", summary="Modifier une page CMS")
async def update_admin_cms_page(
    page_id: str,
    payload: CmsPageUpdate,
    _super=Depends(require_superadmin),
):
    data = payload.model_dump(exclude_unset=True)
    updated = await admin_crud.update_cms_page(page_id, data)
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page CMS introuvable")
    return updated


@router.delete("/{page_id}", summary="Supprimer une page CMS / permission")
async def delete_admin_cms_page(
    page_id: str,
    _super=Depends(require_superadmin),
):
    deleted = await admin_crud.delete_cms_page(page_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page CMS introuvable")
    return {"deleted": True}
