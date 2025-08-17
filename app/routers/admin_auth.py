from fastapi import APIRouter, HTTPException
from app.schemas.admin import AdminLogin, Token
from app.crud.admin import get_by_email
from app.utils.security_admin import verify_password, create_admin_jwt

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

@router.post("/token", response_model=Token)
async def admin_login(form: AdminLogin):
    admin = await get_by_email(form.email)
    if not admin or not verify_password(form.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Bad admin credentials")
    return Token(access_token=create_admin_jwt(admin.email))
