from datetime import datetime, timedelta
from time import time
from urllib.parse import urlencode

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import BackgroundTasks, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jinja2 import Environment, FileSystemLoader
from jose import JWTError, jwt

from app.analytics.service import track_event
from app.config import settings
from app.crud import users as user_crud
from app.schemas.user import UserOut
from app.integrations.meta import build_meta_context, enqueue_complete_registration_event, process_meta_outbox_operation
from app.integrations.meta.service import persisted_meta_context
from app.integrations.meta.schemas import MetaEventContextIn
from app.services.services_store.email import send_email


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
RESEND_COOLDOWN_SECONDS = 120
_last_resend: dict[str, float] = {}
jinja_env = Environment(loader=FileSystemLoader("templates"), autoescape=True)


def create_access_token(sub: str, expires_delta: timedelta) -> str:
    return jwt.encode({"sub": sub, "exp": datetime.utcnow() + expires_delta}, settings.SECRET_KEY, algorithm=ALGORITHM)


def build_url(base_url: str, path: str, params: dict[str, str]) -> str:
    return f"{base_url.rstrip('/')}{path}?{urlencode(params)}"


def build_frontend_url(path: str) -> str:
    return f"{str(settings.FRONTEND_URL).rstrip('/')}/{path.lstrip('/')}"


def build_email_verification_link(token: str) -> str:
    return build_url(str(settings.FRONTEND_URL), "/verify-email", {"token": token})


def build_verify_success_redirect(access_token: str) -> str:
    return build_url(str(settings.FRONTEND_URL), "/verify-success", {"access_token": access_token, "token_type": "bearer", "verified": "true"})


def build_verify_failure_redirect() -> str:
    return build_frontend_url("/email-verification-failed")


def user_out(user: dict) -> UserOut:
    return UserOut(
        id=str(user["_id"]),
        email=user["email"],
        full_name=user.get("full_name"),
        is_active=user["is_active"],
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at"),
    )


async def signup(db, user_in, background_tasks: BackgroundTasks, request: Request) -> UserOut:
    if await user_crud.get_user_by_email(db, user_in.email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cet email est deja utilise.")
    meta_context = build_meta_context(request, user_in.meta)
    user_in.meta = MetaEventContextIn.model_validate(persisted_meta_context(meta_context))
    created = await user_crud.create_user(db, user_in)
    created["meta_context"] = persisted_meta_context(meta_context)
    user_id = str(created["_id"])
    token = create_access_token(user_id, timedelta(hours=1))
    verify_link = build_email_verification_link(token)
    template = jinja_env.get_template("verify_email.html")
    html_body = template.render(user_email=user_in.email, verification_link=verify_link, logo_url=settings.LOGO_URL)
    text_body = (
        f"Bonjour {user_in.email},\n\n"
        "Merci pour votre inscription ! Cliquez sur ce lien pour verifier votre adresse email :\n\n"
        f"{verify_link}\n\nCe lien expire dans 1 heure.\n\nL'equipe Savage Rise"
    )
    background_tasks.add_task(send_email, subject="Bienvenue chez Savage Rise - Verifiez votre email", recipient=user_in.email, body=text_body, html=html_body)
    if await enqueue_complete_registration_event(db, created, meta_context=meta_context):
        background_tasks.add_task(process_meta_outbox_operation, db, f"meta:registration:{user_id}")
    await track_event(db, "account_created", user_id=user_id, metadata={"email_domain": user_in.email.split("@")[-1]}, request=request)
    return user_out(created)


async def login_token(db, form, request: Request):
    user = await user_crud.get_user_by_email(db, form.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_CREDENTIALS", headers={"WWW-Authenticate": "Bearer"})
    if not user.get("is_active", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="EMAIL_NOT_VERIFIED", headers={"WWW-Authenticate": "Bearer"})
    verified = await user_crud.verify_user(db, form.username, form.password)
    if not verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_CREDENTIALS", headers={"WWW-Authenticate": "Bearer"})
    access_token = create_access_token(str(user["_id"]), timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    await track_event(db, "login", user_id=str(user["_id"]), metadata={"email_domain": user.get("email", "").split("@")[-1]}, request=request)
    return {"access_token": access_token, "token_type": "bearer"}


async def verify_email(db, token: str, request: Request):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise JWTError()
        user_oid = ObjectId(user_id)
    except (JWTError, InvalidId):
        return RedirectResponse(build_verify_failure_redirect(), status_code=302)
    user = await user_crud.get_user_by_id(db, user_oid)
    if not user:
        return RedirectResponse(build_verify_failure_redirect(), status_code=302)
    await user_crud.mark_email_verified(db, user_id)
    await track_event(db, "email_verified", user_id=user_id, request=request)
    access_token = create_access_token(user_id, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return RedirectResponse(build_verify_success_redirect(access_token), status_code=302)


async def forgot_password(db, payload, background_tasks: BackgroundTasks):
    user = await user_crud.get_user_by_email(db, payload.email)
    if user:
        token = create_access_token(str(user["_id"]), timedelta(hours=1))
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        template = jinja_env.get_template("reset_password.html")
        html_body = template.render(user_email=payload.email, reset_link=reset_link, logo_url=settings.LOGO_URL)
        body = (
            "Bonjour,\n\nVous avez demande la reinitialisation de votre mot de passe.\n"
            f"Cliquez sur ce lien pour en choisir un nouveau (valable 1 heure) :\n\n{reset_link}\n\n"
            "Si vous n'etes pas a l'origine de cette demande, ignorez cet email.\n\n- L'equipe Savage Rise"
        )
        background_tasks.add_task(send_email, subject="Savage Rise - Reinitialisation de votre mot de passe", recipient=payload.email, body=body, html=html_body)
    return {"message": "Si ce compte existe, vous recevrez un email de reinitialisation."}


async def reset_password(db, payload):
    try:
        data = jwt.decode(payload.token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = data.get("sub")
        if not user_id:
            raise JWTError()
    except JWTError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token invalide ou expire")
    success = await user_crud.update_user_password(db, user_id, payload.new_password)
    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
    return {"message": "Votre mot de passe a bien ete reinitialise."}


async def resend_verification(db, payload, background_tasks: BackgroundTasks):
    email = payload.email.strip().lower()
    now = time()
    last = _last_resend.get(email, 0)
    if now - last < RESEND_COOLDOWN_SECONDS:
        return {"message": "Si ce compte existe, un email a deja ete envoye recemment."}
    _last_resend[email] = now
    user = await user_crud.get_user_by_email(db, email)
    if not user:
        return {"message": "Si ce compte existe, un email de verification sera envoye."}
    if user.get("is_active", False):
        return {"message": "Ce compte est deja verifie."}
    token = create_access_token(str(user["_id"]), timedelta(hours=1))
    verify_link = build_email_verification_link(token)
    template = jinja_env.get_template("verify_email.html")
    html_body = template.render(user_email=email, verification_link=verify_link, logo_url=settings.LOGO_URL)
    text_body = (
        f"Bonjour {email},\n\nVoici un nouveau lien pour verifier votre adresse email :\n\n"
        f"{verify_link}\n\nCe lien expire dans 1 heure.\n\nL'equipe Savage Rise"
    )
    background_tasks.add_task(send_email, subject="Savage Rise - Renvoi : verifiez votre email", recipient=email, body=text_body, html=html_body)
    return {"message": "Si ce compte existe, un email de verification a ete envoye."}
