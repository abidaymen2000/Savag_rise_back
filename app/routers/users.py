from fastapi import APIRouter, Depends, HTTPException, status
from .. import crud, schemas
from ..db import get_db

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(user: schemas.UserCreate, db=Depends(get_db)):
    if await crud.get_user_by_email(db, user.email):
        raise HTTPException(400, "Email déjà utilisé")
    created = await crud.create_user(db, user)
    return {"id": str(created["_id"]), **user.dict(), "is_active": created["is_active"]}

@router.get("/{user_id}", response_model=schemas.UserOut)
async def read_user(user_id: str, db=Depends(get_db)):
    user = await crud.get_user_by_email(db, user_id)  # ou find by _id
    if not user:
        raise HTTPException(404, "Utilisateur non trouvé")
    return {"id": str(user["_id"]), "email": user["email"], "is_active": user["is_active"]}
