import logging

from app.config import settings
from app.core.mongo_init import init_mongo_database
from app.db import client


logger = logging.getLogger("startup")


async def init_mongo() -> None:
    db = client[settings.MONGODB_DB_NAME]
    await init_mongo_database(db)
