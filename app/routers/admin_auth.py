from fastapi import APIRouter, Depends, HTTPException, status
from app.crud.admin import get_by_email, list_cms_pages, update_password_hash
from app.dependencies_admin import admin_capabilities, admin_nav_items, get_current_admin
from app.schemas.admin import AdminLogin, AdminPasswordChange, AdminPublic, Token
from app.utils.security_admin import create_admin_jwt, hash_password, verify_password

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

@router.post("/token", response_model=Token)
async def admin_login(form: AdminLogin):
    admin = await get_by_email(form.email)
    if not admin or not admin.is_active or not verify_password(form.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Bad admin credentials")
    return Token(access_token=create_admin_jwt(admin.email))


@router.get("/me", response_model=AdminPublic)
async def admin_me(current_admin=Depends(get_current_admin)):
    return AdminPublic(
        id=current_admin.id,
        email=current_admin.email,
        full_name=current_admin.full_name,
        is_active=current_admin.is_active,
        is_superadmin=current_admin.is_superadmin,
        permissions=current_admin.permissions,
        capabilities=await admin_capabilities(current_admin),
        available_permissions=await list_cms_pages(),
        nav_items=await admin_nav_items(current_admin),
    )

@router.patch("/change-password", summary="Modifier le mot de passe de l'admin connectÃ©")
async def change_admin_password(
    payload: AdminPasswordChange,
    current_admin=Depends(get_current_admin),
):
    if not verify_password(payload.current_password, current_admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect"
        )

    if verify_password(payload.new_password, current_admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le nouveau mot de passe doit Ãªtre diffÃ©rent de l'ancien"
        )

    updated = await update_password_hash(
        current_admin.email,
        hash_password(payload.new_password)
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ã‰chec de mise Ã  jour du mot de passe"
        )

    return {"message": "Mot de passe admin mis Ã  jour"}
