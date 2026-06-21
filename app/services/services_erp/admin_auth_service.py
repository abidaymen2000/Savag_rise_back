from fastapi import HTTPException, status

from app.crud.admin import get_by_email, list_cms_pages, update_password_hash
from app.dependencies_admin import admin_capabilities, admin_nav_items
from app.schemas.admin import AdminPublic, Token
from app.services.services_erp.security_admin import create_admin_jwt, hash_password, verify_password


async def login(form) -> Token:
    admin = await get_by_email(form.email)
    if not admin or not admin.is_active or not verify_password(form.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Bad admin credentials")
    return Token(access_token=create_admin_jwt(admin.email))


async def me(current_admin) -> AdminPublic:
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


async def change_password(payload, current_admin):
    if not verify_password(payload.current_password, current_admin.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mot de passe actuel incorrect")
    if verify_password(payload.new_password, current_admin.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le nouveau mot de passe doit etre different de l'ancien")
    updated = await update_password_hash(current_admin.email, hash_password(payload.new_password))
    if not updated:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Echec de mise a jour du mot de passe")
    return {"message": "Mot de passe admin mis a jour"}
