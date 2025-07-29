# app/routers/auth.py
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt
from ..config import settings
from ..db import get_db
from ..crud.users import verify_user
from bson import ObjectId

# → Mets ces valeurs en variables d'env
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

router = APIRouter(prefix="/auth", tags=["auth"])

def create_access_token(sub: str):
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": sub, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/token")
async def login_token(
    form: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db),
):
    # form.username == email
    user = await verify_user(db, form.username, form.password)
    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(str(user["_id"]))
    return {"access_token": token, "token_type": "bearer"}
