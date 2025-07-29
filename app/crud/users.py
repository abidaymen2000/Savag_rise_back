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

async def verify_user(db, email: str, password: str):
    user = await db["users"].find_one({"email": email})
    if user and pwd_context.verify(password, user["hashed_password"]):
        return user
    return None

async def mark_email_verified(db, user_id: str):
    oid = ObjectId(user_id)
    await db["users"].update_one(
        {"_id": oid},
        {"$set": {"is_active": True, "is_verified": True}}
    )

async def get_user_by_id(db, oid: ObjectId):
    return await db["users"].find_one({"_id": oid})
