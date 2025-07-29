# app/dependencies.py

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from bson import ObjectId

from app.config import settings
from app.crud.users import get_user_by_id
from app.db import get_db

# Scheme HTTP Bearer → Swagger UI proposera un unique champ "Value"
bearer_scheme = HTTPBearer()

ALGORITHM = "HS256"
SECRET_KEY = settings.SECRET_KEY

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db=Depends(get_db),
):
    """
    Dépendance qui extrait le JWT du header Authorization,
    le décode, vérifie l'utilisateur et son statut.
    """
    token = creds.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise JWTError()
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Convertit en ObjectId et récupère l'utilisateur
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ID utilisateur dans le token invalide",
        )

    user = await get_user_by_id(db, oid)
    if not user or not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou inactif",
        )

    return user
