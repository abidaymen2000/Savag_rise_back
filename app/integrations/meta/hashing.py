import hashlib
import re
from typing import Optional


SPACE_RE = re.compile(r"\s+")


def _clean_text(value: object) -> Optional[str]:
    if value is None:
        return None
    text = SPACE_RE.sub(" ", str(value).strip())
    return text or None


def normalize_email(value: object) -> Optional[str]:
    text = _clean_text(value)
    return text.lower() if text else None


def normalize_phone(value: object) -> Optional[str]:
    text = _clean_text(value)
    if not text:
        return None
    digits = re.sub(r"[^\d+]", "", text)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("+"):
        digits = digits[1:]
    digits = re.sub(r"\D", "", digits)
    if len(digits) == 8:
        digits = f"216{digits}"
    if digits.startswith("216") and len(digits) == 11:
        return digits
    return digits or None


def normalize_name(value: object) -> Optional[str]:
    text = _clean_text(value)
    return text.lower() if text else None


def normalize_city(value: object) -> Optional[str]:
    text = _clean_text(value)
    return text.lower() if text else None


def normalize_country(value: object) -> Optional[str]:
    text = _clean_text(value)
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"tunisia", "tunisie", "tn"}:
        return "tn"
    return lowered


def normalize_external_id(value: object) -> Optional[str]:
    text = _clean_text(value)
    return text.lower() if text else None


def sha256_hexdigest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalized_sha256(value: object, *, normalizer) -> Optional[str]:
    normalized = normalizer(value)
    if not normalized:
        return None
    return sha256_hexdigest(normalized)
