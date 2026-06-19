from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import Request

from app.analytics.events import ALLOWED_ANALYTICS_EVENTS

SOCIAL_SOURCES = {
    "instagram": ("instagram.", "l.instagram.com"),
    "facebook": ("facebook.", "fb.com", "lm.facebook.com"),
    "tiktok": ("tiktok.", "t.co"),
    "google": ("google.", "googleadservices."),
}

_rate_limit_hits: dict[str, list[datetime]] = {}
RATE_LIMIT_MAX_EVENTS = 120
RATE_LIMIT_WINDOW_SECONDS = 60


def is_allowed_event(event_name: Optional[str]) -> bool:
    return bool(event_name and event_name in ALLOWED_ANALYTICS_EVENTS)


def get_client_ip(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else None


def request_metadata(request: Optional[Request]) -> dict[str, Optional[str]]:
    if not request:
        return {"ip_address": None, "user_agent": None, "referrer": None}
    return {
        "ip_address": get_client_ip(request),
        "user_agent": request.headers.get("user-agent"),
        "referrer": request.headers.get("referer") or request.headers.get("referrer"),
    }


def derive_source(metadata: Optional[Dict[str, Any]], referrer: Optional[str]) -> str:
    data = metadata or {}
    explicit = data.get("source") or data.get("utm_source")
    if explicit:
        return str(explicit).strip().lower()
    if not referrer:
        return "direct"
    host = (urlparse(referrer).hostname or "").lower()
    for source, markers in SOCIAL_SOURCES.items():
        if any(marker in host for marker in markers):
            return source
    return host.replace("www.", "") if host else "direct"


def extract_utm_campaign(metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    campaign = (metadata or {}).get("utm_campaign")
    return str(campaign).strip() if campaign else None


def rate_limit_allows(key: Optional[str]) -> bool:
    if not key:
        return True
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    hits = [hit for hit in _rate_limit_hits.get(key, []) if hit >= cutoff]
    if len(hits) >= RATE_LIMIT_MAX_EVENTS:
        _rate_limit_hits[key] = hits
        return False
    hits.append(now)
    _rate_limit_hits[key] = hits
    return True
