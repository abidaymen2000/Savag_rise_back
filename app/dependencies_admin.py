from typing import Callable

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from app.config import settings
from app.crud.admin import get_by_email, get_permission_keys, list_cms_pages
from app.models.admin import AdminInDB

bearer_admin = HTTPBearer(auto_error=True)

ROOT_SUPERADMIN_EMAIL = "savage.rise.tn@gmail.com"
def is_superadmin(admin: AdminInDB) -> bool:
    return bool(admin.is_superadmin) or admin.email.lower() == ROOT_SUPERADMIN_EMAIL


async def admin_capabilities(admin: AdminInDB) -> dict[str, bool]:
    permission_keys = await get_permission_keys()
    if is_superadmin(admin):
        return {permission: True for permission in permission_keys}
    granted = set(admin.permissions or [])
    return {permission: permission in granted for permission in permission_keys}


async def admin_nav_items(admin: AdminInDB) -> list[dict]:
    pages = await list_cms_pages()
    if is_superadmin(admin):
        return pages
    granted = set(admin.permissions or [])
    return [
        page for page in pages
        if not page.get("requires_permission", True) or page["key"] in granted
    ]

async def get_current_admin(
    creds: HTTPAuthorizationCredentials = Security(bearer_admin),
) -> AdminInDB:
    token = creds.credentials
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("scope") != "admin":
            raise cred_exc
        email = payload.get("sub")
        if not email:
            raise cred_exc
    except JWTError:
        raise cred_exc

    admin = await get_by_email(email)
    if not admin or not admin.is_active:
        raise cred_exc
    return admin


async def require_superadmin(current_admin: AdminInDB = Depends(get_current_admin)) -> AdminInDB:
    if not is_superadmin(current_admin):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "code": "ADMIN_SUPERADMIN_REQUIRED",
                "message": "Acces super admin requis",
            },
        )
    return current_admin


def require_permission(permission: str) -> Callable:
    async def _dependency(current_admin: AdminInDB = Depends(get_current_admin)) -> AdminInDB:
        if is_superadmin(current_admin):
            return current_admin
        active_permissions = set(await get_permission_keys())
        granted_permissions = set(current_admin.permissions or [])
        if permission not in active_permissions or permission not in granted_permissions:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                {
                    "code": "ADMIN_PERMISSION_DENIED",
                    "message": "Permission admin insuffisante",
                    "required_permission": permission,
                    "permissions": current_admin.permissions or [],
                    "capabilities": await admin_capabilities(current_admin),
                },
            )
        return current_admin

    return _dependency
