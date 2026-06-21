from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.db import get_db
from app.schemas.user import PasswordReset, PasswordResetRequest, UserCreate, UserOut
from app.services.services_store import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Creer un compte et envoyer un email de verification")
async def signup(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db=Depends(get_db),
):
    return await auth_service.signup(db, user_in, background_tasks, request)


@router.post("/token", summary="Obtenir un JWT apres login (email verifie requis)")
async def login_token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db),
):
    return await auth_service.login_token(db, form, request)


@router.get("/verify-email", summary="Verifier un email")
async def verify_email(request: Request, token: str = Query(...), db=Depends(get_db)):
    return await auth_service.verify_email(db, token, request)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED, summary="Demande de reset de mot de passe")
async def forgot_password(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    return await auth_service.forgot_password(db, request, background_tasks)


@router.post("/reset-password", status_code=status.HTTP_200_OK, summary="Reinitialisation du mot de passe via token")
async def reset_password(payload: PasswordReset, db=Depends(get_db)):
    return await auth_service.reset_password(db, payload)


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED, summary="Renvoyer l'email de verification")
async def resend_verification(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    return await auth_service.resend_verification(db, payload, background_tasks)
