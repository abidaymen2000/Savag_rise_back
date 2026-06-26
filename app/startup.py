import logging

from app.config import settings
from app.core.mongo_init import init_mongo_database
from app.db import client


logger = logging.getLogger("startup")


async def ensure_mongo_transaction_support() -> None:
    hello = await client.admin.command("hello")
    supports_sessions = hello.get("logicalSessionTimeoutMinutes") is not None
    is_replica_set = bool(hello.get("setName"))
    if supports_sessions and is_replica_set:
        logger.info("Mongo transactions supported: replica set=%s", hello.get("setName"))
        return
    message = (
        "MongoDB transactions are not supported by the current deployment. "
        "Savage Rise order/stock atomicity requires a replica set with sessions enabled."
    )
    if settings.REQUIRE_MONGO_TRANSACTIONS:
        raise RuntimeError(message)
    logger.warning(message)


async def init_mongo() -> None:
    db = client[settings.MONGODB_DB_NAME]
    await ensure_mongo_transaction_support()
    await init_mongo_database(db)
