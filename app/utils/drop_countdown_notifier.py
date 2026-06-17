import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from bson import ObjectId
from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.db import client
from app.routers.drop_countdown import (
    DROP_COUNTDOWN_KEY,
    SETTINGS_COLLECTION,
    SUBSCRIBERS_COLLECTION,
    drop_key_from_value,
)
from app.utils.email import send_email

logger = logging.getLogger("drop_countdown")

CHECK_INTERVAL_SECONDS = 30
SEND_CLAIM_TTL_MINUTES = 30

jinja_env = Environment(loader=FileSystemLoader("templates"), autoescape=True)


def _frontend_url(path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return f"{str(settings.FRONTEND_URL).rstrip('/')}/{path_or_url.lstrip('/')}"


def _render_email(value: Dict[str, Any], recipient_email: str) -> tuple[str, str]:
    cta_url = _frontend_url(value.get("cta_url") or "/products")
    template = jinja_env.get_template("drop_release.html")
    html = template.render(
        drop_name=value.get("drop_name") or "Savage Rise Drop",
        title=value.get("title") or "Le drop est disponible",
        subtitle=value.get("subtitle"),
        preview=value.get("email_preview"),
        cta_label=value.get("cta_label") or "Shop the drop",
        cta_url=cta_url,
        recipient_email=recipient_email,
        logo_url=settings.LOGO_URL,
    )
    text = (
        f"{value.get('drop_name') or 'Savage Rise Drop'} est disponible.\n\n"
        f"{value.get('email_preview') or value.get('subtitle') or ''}\n\n"
        f"{cta_url}\n\n"
        "L'equipe Savage Rise"
    )
    return text, html


async def send_due_drop_notification_once() -> bool:
    db = client[settings.MONGODB_DB_NAME]
    now = datetime.utcnow()
    stale_claim_before = now - timedelta(minutes=SEND_CLAIM_TTL_MINUTES)

    claim = await db[SETTINGS_COLLECTION].find_one_and_update(
        {
            "_id": DROP_COUNTDOWN_KEY,
            "value.is_active": True,
            "value.email_enabled": True,
            "value.launch_at": {"$lte": now},
            "notification_sent_at": {"$exists": False},
            "$or": [
                {"notification_status": {"$exists": False}},
                {"notification_status": {"$ne": "sending"}},
                {"notification_claimed_at": {"$lte": stale_claim_before}},
            ],
        },
        {
            "$set": {
                "notification_status": "sending",
                "notification_claimed_at": now,
            }
        },
    )
    if not claim:
        return False

    value = claim["value"]
    drop_key = drop_key_from_value(value)
    subscriptions = await db[SUBSCRIBERS_COLLECTION].find(
        {"drop_key": drop_key},
        {"user_id": 1, "email": 1},
    ).to_list(length=20000)
    user_ids = []
    fallback_emails: Dict[str, str] = {}
    for subscription in subscriptions:
        user_id = subscription.get("user_id")
        if not user_id:
            continue
        fallback_emails[user_id] = subscription.get("email")
        try:
            user_ids.append(ObjectId(user_id))
        except Exception:
            continue

    users = await db["users"].find(
        {
            "_id": {"$in": user_ids},
            "email": {"$exists": True, "$ne": None},
            "is_active": True,
        },
        {"email": 1},
    ).to_list(length=20000)

    sent_count = 0
    failure_count = 0
    subject = value.get("email_subject") or "Le nouveau drop Savage Rise est disponible"

    for user in users:
        email = user.get("email") or fallback_emails.get(str(user["_id"]))
        if not email:
            continue
        try:
            text, html = _render_email(value, email)
            await asyncio.to_thread(
                send_email,
                subject=subject,
                recipient=email,
                body=text,
                html=html,
            )
            sent_count += 1
        except Exception:
            failure_count += 1
            logger.exception("Failed to send drop release email to %s", email)

    await db[SETTINGS_COLLECTION].update_one(
        {"_id": DROP_COUNTDOWN_KEY},
        {
            "$set": {
                "notification_status": "sent",
                "notification_sent_at": datetime.utcnow(),
                "notification_recipients_count": sent_count,
                "notification_failures_count": failure_count,
            }
        },
    )
    logger.info("Drop notification sent to %s users, %s failures", sent_count, failure_count)
    return True


async def drop_countdown_monitor_loop() -> None:
    while True:
        try:
            await send_due_drop_notification_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Drop countdown monitor failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
