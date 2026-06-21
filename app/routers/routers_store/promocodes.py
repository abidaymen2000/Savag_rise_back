from typing import Optional

from fastapi import APIRouter, Depends

from app.db import get_db
from app.dependencies import get_current_user_optional
from app.schemas.promocode import ApplyRequest, ApplyResponse
from app.services.services_store import promocode_service


router = APIRouter(prefix="/promocodes", tags=["Promo Codes"])


@router.post("/apply", response_model=ApplyResponse, summary="Verifier/appliquer un code promo (public)")
async def apply_code(
    payload: ApplyRequest,
    db=Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    return await promocode_service.apply_code(db, payload, current_user)
