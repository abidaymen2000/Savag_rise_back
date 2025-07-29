# app/routers/auth.py
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from bson import ObjectId

from app.config import settings
from app.db import get_db
from app.crud.users import create_user, get_user_by_email, update_user_password, verify_user, mark_email_verified
from app.schemas.user import PasswordReset, PasswordResetRequest, UserCreate, UserOut
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
        # 0) Vérification d’unicité de l’email
    if await get_user_by_email(db, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet email est déjà utilisé."
        )
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

@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED,
             summary="Demande de reset de mot de passe")
async def forgot_password(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    user = await get_user_by_email(db, request.email)
    # On ne révèle pas si l'email existe ou non
    if user:
        # Génère un token valable 1h
        token = create_access_token(str(user["_id"]), timedelta(hours=1))
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        subject = "Savage Rise – Réinitialisation de votre mot de passe"
        body = (
            f"Bonjour,\n\n"
            "Vous avez demandé la réinitialisation de votre mot de passe.\n"
            f"Cliquez sur ce lien pour en choisir un nouveau (valable 1 heure) :\n\n"
            f"{reset_link}\n\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n\n"
            "— L'équipe Savage Rise"
        )
        background_tasks.add_task(send_email, subject, request.email, body)

    return {"message": "Si ce compte existe, vous recevrez un email de réinitialisation."}


@router.post("/reset-password", status_code=status.HTTP_200_OK,
             summary="Réinitialisation du mot de passe via token")
async def reset_password(
    payload: PasswordReset,
    db=Depends(get_db),
):
    # 1) Décodage du token
    try:
        data = jwt.decode(payload.token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = data.get("sub")
        if not user_id:
            raise JWTError()
    except JWTError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token invalide ou expiré")

    # 2) Met à jour le mot de passe
    success = await update_user_password(db, user_id, payload.new_password)
    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")

    return {"message": "Votre mot de passe a bien été réinitialisé."}