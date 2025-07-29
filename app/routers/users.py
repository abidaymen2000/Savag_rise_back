# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from .. import crud, schemas
from ..db import get_db

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}", response_model=schemas.UserOut)
async def read_user(user_id: str, db=Depends(get_db)):
    user = await crud.get_user_by_id(db, user_id)  # ou find by _id
    if not user:
        raise HTTPException(404, "Utilisateur non trouvé")
    return {"id": str(user["_id"]), "email": user["email"], "is_active": user["is_active"]}
