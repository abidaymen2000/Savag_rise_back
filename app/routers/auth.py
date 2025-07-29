# app/routers/auth.py
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from bson import ObjectId

from app.config import settings
from app.db import get_db
from app.crud.users import create_user, verify_user, mark_email_verified
from app.schemas.user import UserCreate, UserOut
from app.utils.email import send_email

router = APIRouter(prefix="/auth", tags=["auth"])

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(sub: str, expires_delta: timedelta) -> str:
    to_encode = {
        "sub": sub,
        "exp": datetime.utcnow() + expires_delta
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte et envoyer un email de vérification"
)
async def signup(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    # 1) Création du user (is_active=False tant que non vérifié)
    created = await create_user(db, user_in)
    user_id = str(created["_id"])

    # 2) Génération du token de vérification (valable 1h)
    token = create_access_token(user_id, timedelta(hours=1))
    verify_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"

    # 3) Envoi de l’email en tâche de fond
    subject = "Bienvenue chez Savage Rise – Vérifiez votre email"
    body = (
        f"Bonjour {user_in.email},\n\n"
        "Merci pour votre inscription ! Cliquez sur ce lien pour vérifier votre adresse email :\n\n"
        f"{verify_link}\n\n"
        "Ce lien expire dans 1 heure.\n\n"
        "L'équipe Savage Rise"
    )
    background_tasks.add_task(send_email, subject, user_in.email, body)

    return UserOut(id=user_id, email=user_in.email, is_active=False)


@router.post(
    "/token",
    summary="Obtenir un JWT après login (email vérifié requis)"
)
async def login_token(
    form: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db),
):
    user = await verify_user(db, form.username, form.password)
    if not user or not user.get("is_active", False):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Email non vérifié ou identifiants invalides",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        str(user["_id"]),
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get(
    "/verify-email",
    summary="Vérifier un email via token",
    status_code=status.HTTP_200_OK
)
async def verify_email(
    token: str = Query(..., description="Token de vérification reçu par email"),
    db=Depends(get_db),
):
    # Décodage du token
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise JWTError()
    except JWTError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Token invalide ou expiré"
        )

    # Activation du user en base
    await mark_email_verified(db, user_id)

    return {"message": "Votre email a bien été vérifié. Vous pouvez maintenant vous connecter."}
