from fastapi import APIRouter, Depends

from app.dependencies_admin import get_current_admin
from app.schemas.admin import AdminLogin, AdminPasswordChange, AdminPublic, Token
from app.services.services_erp import admin_auth_service


router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.post("/token", response_model=Token)
async def admin_login(form: AdminLogin):
    return await admin_auth_service.login(form)


@router.get("/me", response_model=AdminPublic)
async def admin_me(current_admin=Depends(get_current_admin)):
    return await admin_auth_service.me(current_admin)


@router.patch("/change-password", summary="Modifier le mot de passe de l'admin connecte")
async def change_admin_password(payload: AdminPasswordChange, current_admin=Depends(get_current_admin)):
    return await admin_auth_service.change_password(payload, current_admin)
