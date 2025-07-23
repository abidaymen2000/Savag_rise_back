from passlib.context import CryptContext
from bson import ObjectId
from ..schemas import UserCreate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_user_by_email(db, email: str):
    return await db["users"].find_one({"email": email})

async def create_user(db, user: UserCreate):
    hashed = pwd_context.hash(user.password)
    doc = {
        "email": user.email,
        "hashed_password": hashed,
        "is_active": True
    }
    res = await db["users"].insert_one(doc)
    return await db["users"].find_one({"_id": res.inserted_id})
