# app/routers/auth.py
from datetime import datetime, timedelta
from time import time
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from jinja2 import Environment, FileSystemLoader
from jose import jwt, JWTError
from bson import ObjectId
from bson.errors import InvalidId

from app.analytics.service import track_event
from app.config import settings
from app.db import get_db
from app.crud.users import create_user, get_user_by_email, get_user_by_id, update_user_password, verify_user, mark_email_verified
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


def build_url(base_url: str, path: str, params: dict[str, str]) -> str:
    return f"{base_url.rstrip('/')}{path}?{urlencode(params)}"


def build_email_verification_link(token: str) -> str:
    return build_url(settings.BACKEND_URL, "/auth/verify-email", {"token": token})


def build_verify_success_redirect(token: str) -> str:
    return build_url(
        settings.FRONTEND_URL,
        "/verify-success",
        {
            "verified": "success",
            "token": token,
            "access_token": token,
            "token_type": "bearer",
        },
    )


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte et envoyer un email de vérification"
)
async def signup(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
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
    verify_link = build_email_verification_link(token)

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

    await track_event(
        db,
        "account_created",
        user_id=user_id,
        metadata={"email_domain": user_in.email.split("@")[-1]},
        request=request,
    )

    return UserOut(
        id=user_id,
        email=created["email"],
        full_name=created.get("full_name"),
        is_active=created["is_active"],
        created_at=created.get("created_at"),
        updated_at=created.get("updated_at"),
    )

@router.post(
    "/token",
    summary="Obtenir un JWT après login (email vérifié requis)"
)
async def login_token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db),
):
    # 1) Récupérer l'utilisateur par email
    user = await get_user_by_email(db, form.username)
    if not user:
        # Ne révèle pas l'existence → message générique
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_CREDENTIALS",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2) Email non vérifié
    if not user.get("is_active", False):
        # Code explicite pour que le front sache réagir
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,   # ou 403 si tu préfères
            detail="EMAIL_NOT_VERIFIED",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3) Vérifier le mot de passe (l'utilisateur est actif à ce stade)
    verified = await verify_user(db, form.username, form.password)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_CREDENTIALS",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4) OK → token
    access_token = create_access_token(
        str(user["_id"]),
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    await track_event(
        db,
        "login",
        user_id=str(user["_id"]),
        metadata={"email_domain": user.get("email", "").split("@")[-1]},
        request=request,
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
        user_oid = ObjectId(user_id)
    except (JWTError, InvalidId):
        # renvoie vers home avec erreur
        return RedirectResponse(f"{settings.FRONTEND_URL}/?verified=error", status_code=302)

    user = await get_user_by_id(db, user_oid)
    if not user:
        return RedirectResponse(f"{settings.FRONTEND_URL}/?verified=error", status_code=302)

    # 2) Marquer l'email comme vérifié
    await mark_email_verified(db, user_id)

    # 3) Générer un access token “classique”
    access_token = create_access_token(user_id, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    # 4) Rediriger vers le front avec le token dans la query
    return RedirectResponse(build_verify_success_redirect(access_token), status_code=302)

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
        template = jinja_env.get_template("reset_password.html")
        html_body = template.render(
            user_email=request.email,
            reset_link=reset_link,
            logo_url=settings.LOGO_URL
        )
        subject = "Savage Rise – Réinitialisation de votre mot de passe"
        body = (
            f"Bonjour,\n\n"
            "Vous avez demandé la réinitialisation de votre mot de passe.\n"
            f"Cliquez sur ce lien pour en choisir un nouveau (valable 1 heure) :\n\n"
            f"{reset_link}\n\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n\n"
            "— L'équipe Savage Rise"
        )
        background_tasks.add_task(
            send_email,
            subject=subject,
            recipient=request.email,
            body=body,
            html=html_body
        )

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
    verify_link = build_email_verification_link(token)

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
