import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from bson import ObjectId
from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.crud import drop_countdown as countdown_crud
from app.db import client
from app.services.services_store.email import send_email

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


def drop_key_from_value(value: dict) -> str:
    launch_at = value["launch_at"]
    if isinstance(launch_at, datetime):
        launch_part = launch_at.isoformat()
    else:
        launch_part = str(launch_at)
    return f"{value.get('drop_name', 'drop')}::{launch_part}"


async def send_due_drop_notification_once() -> bool:
    db = client[settings.MONGODB_DB_NAME]
    now = datetime.utcnow()
    stale_claim_before = now - timedelta(minutes=SEND_CLAIM_TTL_MINUTES)

    claim = await countdown_crud.claim_due_drop_notification(db, now, stale_claim_before)
    if not claim:
        return False

    value = claim["value"]
    drop_key = drop_key_from_value(value)
    subscriptions = await countdown_crud.list_drop_subscriptions(db, drop_key, limit=20000)
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

    users = await countdown_crud.list_active_users_with_email(db, user_ids, limit=20000)

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

    await countdown_crud.mark_drop_notification_sent(db, sent_count, failure_count, datetime.utcnow())
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
