from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.config import settings
from app.crud.admin import get_by_email
from app.models.admin import AdminInDB

oauth2_admin = OAuth2PasswordBearer(tokenUrl="/admin/auth/token")

async def get_current_admin(token: str = Depends(oauth2_admin)) -> AdminInDB:
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
    if not admin:
        raise cred_exc
    return admin
