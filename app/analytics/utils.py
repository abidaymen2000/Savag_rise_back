import ipaddress
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import Request

from app.analytics.events import ALLOWED_ANALYTICS_EVENTS
from app.config import settings

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


def _parse_ip(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _is_trusted_proxy_host(host: Optional[str]) -> bool:
    parsed = _parse_ip(host)
    if not parsed:
        return False
    ip_obj = ipaddress.ip_address(parsed)
    return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local


def get_client_ip(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    direct_host = _parse_ip(request.client.host) if request.client else None
    forwarded_for = request.headers.get("x-forwarded-for")
    if settings.TRUST_PROXY_HEADERS and forwarded_for and _is_trusted_proxy_host(direct_host):
        forwarded_chain = [_parse_ip(part) for part in forwarded_for.split(",")]
        forwarded_chain = [part for part in forwarded_chain if part]
        if forwarded_chain:
            index = max(len(forwarded_chain) - settings.TRUSTED_PROXY_HOPS, 0)
            selected = forwarded_chain[index]
            if selected:
                return selected
    real_ip = _parse_ip(request.headers.get("x-real-ip"))
    if real_ip and _is_trusted_proxy_host(direct_host):
        return real_ip
    return direct_host


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
