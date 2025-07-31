from typing import Optional
from passlib.context import CryptContext
from bson import ObjectId
from app.schemas.user import UserCreate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_user(db, user_in: UserCreate):
    hashed = pwd_context.hash(user_in.password)
    doc = {
        "email": user_in.email,
        "hashed_password": hashed,
        "is_active": False,      # bloqué tant que non vérifié
        "is_verified": False
    }
    res = await db["users"].insert_one(doc)
    return await db["users"].find_one({"_id": res.inserted_id})

async def verify_user(db, email: str, password: str) -> Optional[dict]:
    """
    Vérifie qu'un utilisateur existe, que son mot de passe est présent et valide.
    """
    user = await db["users"].find_one({"email": email})
    if not user:
        return None

    hashed = user.get("hashed_password")
    # Soit il n'existe pas, soit on ne peut pas vérifier
    if not hashed or not pwd_context.verify(password, hashed):
        return None

    return user

async def mark_email_verified(db, user_id: str):
    oid = ObjectId(user_id)
    await db["users"].update_one(
        {"_id": oid},
        {"$set": {"is_active": True, "is_verified": True}}
    )

async def get_user_by_id(db, oid: ObjectId):
    return await db["users"].find_one({"_id": oid})

async def update_user_password(db, user_id: str, new_password: str) -> bool:
    hashed = pwd_context.hash(new_password)
    result = await db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"hashed_password": hashed}}
    )
    return result.modified_count == 1

async def get_user_by_email(db, email: str) -> Optional[dict]:
    """
    Récupère un utilisateur par email.
    """
    return await db["users"].find_one({"email": email})

async def update_user_profile(db, user_id: str, data: dict) -> Optional[dict]:
    """
    Met à jour les champs passés dans data pour l'utilisateur user_id.
    """
    oid = ObjectId(user_id)
    await db["users"].update_one({"_id": oid}, {"$set": data})
    return await db["users"].find_one({"_id": oid})

async def change_user_password(db, user_id: str, current_password: str, new_password: str) -> bool:
    """
    Vérifie current_password, puis remplace par new_password (hashé).
    """
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not user or not pwd_context.verify(current_password, user["hashed_password"]):
        return False
    hashed = pwd_context.hash(new_password)
    res = await db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"hashed_password": hashed}}
    )
    return res.modified_count == 1