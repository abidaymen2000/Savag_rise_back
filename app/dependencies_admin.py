from typing import Callable

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from app.config import settings
from app.crud.admin import get_by_email
from app.models.admin import AdminInDB

bearer_admin = HTTPBearer(auto_error=True)

ROOT_SUPERADMIN_EMAIL = "savage.rise.tn@gmail.com"
ALL_ADMIN_PERMISSIONS = [
    "orders",
    "shipping",
    "promocodes",
    "loyalty",
    "products",
    "packs",
    "categories",
    "header_video",
    "vlog",
    "engagement",
    "users",
    "admins",
]


def is_superadmin(admin: AdminInDB) -> bool:
    return bool(admin.is_superadmin) or admin.email.lower() == ROOT_SUPERADMIN_EMAIL


def admin_capabilities(admin: AdminInDB) -> dict[str, bool]:
    if is_superadmin(admin):
        return {permission: True for permission in ALL_ADMIN_PERMISSIONS}
    granted = set(admin.permissions or [])
    return {permission: permission in granted for permission in ALL_ADMIN_PERMISSIONS}

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
        if permission not in (current_admin.permissions or []):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                {
                    "code": "ADMIN_PERMISSION_DENIED",
                    "message": "Permission admin insuffisante",
                    "required_permission": permission,
                    "permissions": current_admin.permissions or [],
                    "capabilities": admin_capabilities(current_admin),
                },
            )
        return current_admin

    return _dependency
