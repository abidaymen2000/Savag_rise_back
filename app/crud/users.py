# app/crud/user.py
from passlib.context import CryptContext
from bson import ObjectId

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_user(db, user_create):
    hashed = pwd_context.hash(user_create.password)
    doc = {"email": user_create.email, "password": hashed, "is_active": True}
    res = await db["users"].insert_one(doc)
    return await db["users"].find_one({"_id": res.inserted_id})

async def verify_user(db, email: str, password: str):
    user = await db["users"].find_one({"email": email})
    if not user:
        return None
    if not pwd_context.verify(password, user["password"]):
        return None
    return user

async def get_user_by_id(db, user_id: ObjectId):
    return await db["users"].find_one({"_id": user_id})
