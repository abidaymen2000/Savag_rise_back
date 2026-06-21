from fastapi import APIRouter, Depends

from app.dependencies_admin import get_current_admin, require_superadmin
from app.schemas.admin import CmsPageCreate, CmsPageUpdate
from app.services.services_cms import cms_page_service


router = APIRouter(prefix="/admin/cms-pages", tags=["admin-cms-pages"])


@router.get("/sidebar", summary="Sidebar CMS de l'admin connecte")
async def current_admin_sidebar(current_admin=Depends(get_current_admin)):
    return await cms_page_service.sidebar(current_admin)


@router.get("", summary="Lister les pages CMS")
async def list_admin_cms_pages(_super=Depends(require_superadmin)):
    return await cms_page_service.list_pages()


@router.post("", status_code=201, summary="Creer une page CMS / permission")
async def create_admin_cms_page(
    payload: CmsPageCreate,
    _super=Depends(require_superadmin),
):
    return await cms_page_service.create_page(payload)


@router.patch("/{page_id}", summary="Modifier une page CMS")
async def update_admin_cms_page(
    page_id: str,
    payload: CmsPageUpdate,
    _super=Depends(require_superadmin),
):
    return await cms_page_service.update_page(page_id, payload)


@router.delete("/{page_id}", summary="Supprimer une page CMS / permission")
async def delete_admin_cms_page(
    page_id: str,
    _super=Depends(require_superadmin),
):
    return await cms_page_service.delete_page(page_id)
