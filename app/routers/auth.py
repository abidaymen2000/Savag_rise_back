# app/routers/auth.py
from datetime import datetime, timedelta
from time import time
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from jinja2 import Environment, FileSystemLoader
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

# Cooldown simple (optionnel)
RESEND_COOLDOWN_SECONDS = 120
_last_resend: dict[str, float] = {}  # email -> last timestamp

# Configurez Jinja2 pour charger les templates
jinja_env = Environment(
    loader=FileSystemLoader("templates"),  # dossier où est verify_email.html
    autoescape=True
)

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
    # 0) Email unique
    if await get_user_by_email(db, user_in.email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cet email est déjà utilisé.")

    # 1) Création user (is_active=False)
    created = await create_user(db, user_in)
    user_id = str(created["_id"])

    # 2) Génération du token (1h)
    token = create_access_token(user_id, timedelta(hours=1))
    verify_link = f"{settings.BACKEND_URL}/auth/verify-email?token={token}"

    # 3) Rendu du template HTML
    template = jinja_env.get_template("verify_email.html")
    html_body = template.render(
        user_email=user_in.email,
        verification_link=verify_link,
        logo_url=settings.LOGO_URL
    )

    # 4) Fallback texte brut (optionnel)
    text_body = (
        f"Bonjour {user_in.email},\n\n"
        "Merci pour votre inscription ! Cliquez sur ce lien pour vérifier votre adresse email :\n\n"
        f"{verify_link}\n\n"
        "Ce lien expire dans 1 heure.\n\n"
        "L'équipe Savage Rise"
    )

    # 5) Envoi en background (assurez-vous que send_email peut prendre html_body)
    background_tasks.add_task(
        send_email,
        subject="Bienvenue chez Savage Rise – Vérifiez votre email",
        recipient=user_in.email,
        body=text_body,
        html=html_body              # passez le HTML au handler
    )

    return UserOut(
        id=user_id,
        email=created["email"],
        full_name=created.get("full_name"),
        is_active=created["is_active"],
    )

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


@router.get("/verify-email", summary="Vérifier un email et auto-login")
async def verify_email(token: str = Query(...), db=Depends(get_db)):
    # 1) Décodage du token reçu par email
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise JWTError()
    except JWTError:
        # renvoie vers home avec erreur
        return RedirectResponse(f"{settings.FRONTEND_URL}/?verified=error", status_code=302)

    # 2) Marquer l'email comme vérifié
    await mark_email_verified(db, user_id)

    # 3) Générer un access token “classique”
    access_token = create_access_token(user_id, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    # 4) Rediriger vers le front avec le token dans la query
    return RedirectResponse(f"{settings.FRONTEND_URL}/verify-success?token={access_token}", status_code=302)

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

@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Renvoyer l'email de vérification"
)
async def resend_verification(
    payload: PasswordResetRequest,               # { "email": "..." }
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    email = payload.email.strip().lower()

    # 1) Anti-spam minimal (optionnel)
    now = time()
    last = _last_resend.get(email, 0)
    if now - last < RESEND_COOLDOWN_SECONDS:
        # On renvoie 202 pour ne pas divulguer d'info sensible
        return {"message": "Si ce compte existe, un email a déjà été envoyé récemment."}
    _last_resend[email] = now

    # 2) Récupère l'utilisateur si présent
    user = await get_user_by_email(db, email)

    # Pour ne pas divulguer si l'utilisateur existe, on garde des messages neutres
    if not user:
        return {"message": "Si ce compte existe, un email de vérification sera envoyé."}

    # 3) Si déjà vérifié -> message neutre/utile
    if user.get("is_active", False):
        return {"message": "Ce compte est déjà vérifié."}

    # 4) Génère un nouveau token (1h) + lien
    token = create_access_token(str(user["_id"]), timedelta(hours=1))
    verify_link = f"{settings.BACKEND_URL}/auth/verify-email?token={token}"

    # 5) Email HTML + texte (réutilise ton template verify_email.html)
    template = jinja_env.get_template("verify_email.html")
    html_body = template.render(
        user_email=email,
        verification_link=verify_link,
        logo_url=settings.LOGO_URL
    )
    text_body = (
        f"Bonjour {email},\n\n"
        "Voici un nouveau lien pour vérifier votre adresse email :\n\n"
        f"{verify_link}\n\n"
        "Ce lien expire dans 1 heure.\n\n"
        "L'équipe Savage Rise"
    )

    # 6) Envoi en background
    background_tasks.add_task(
        send_email,
        subject="Savage Rise – Renvoi : vérifiez votre email",
        recipient=email,
        body=text_body,
        html=html_body
    )

    return {"message": "Si ce compte existe, un email de vérification a été envoyé."}