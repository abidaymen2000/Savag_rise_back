import re
from typing import Any, Optional


def meta_safe_id(value: Any) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", str(value).strip())
    return cleaned.strip("-") or "item"


def meta_item_group_id(product_id: str, style_id: Optional[str] = None) -> str:
    return meta_safe_id(style_id or product_id)


def meta_variant_content_id(product_id: str, color: Optional[str] = None, size: Optional[str] = None) -> str:
    parts = [str(product_id).strip()]
    if color:
        parts.append(str(color).strip())
    if size:
        parts.append(str(size).strip())
    return meta_safe_id("-".join(part for part in parts if part))
