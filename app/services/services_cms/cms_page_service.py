from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.crud import admin as admin_crud
from app.dependencies_admin import admin_capabilities, admin_nav_items


async def sidebar(current_admin):
    return {
        "items": await admin_nav_items(current_admin),
        "capabilities": await admin_capabilities(current_admin),
        "permissions": current_admin.permissions or [],
    }


async def list_pages():
    return {"items": await admin_crud.list_cms_pages(include_inactive=True)}


async def create_page(payload):
    data = payload.model_dump()
    if await admin_crud.get_cms_page_by_key(data["key"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "Permission CMS deja existante")
    try:
        return await admin_crud.create_cms_page(data)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Permission CMS deja existante")


async def update_page(page_id: str, payload):
    data = payload.model_dump(exclude_unset=True)
    updated = await admin_crud.update_cms_page(page_id, data)
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page CMS introuvable")
    return updated


async def delete_page(page_id: str):
    deleted = await admin_crud.delete_cms_page(page_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page CMS introuvable")
    return {"deleted": True}
