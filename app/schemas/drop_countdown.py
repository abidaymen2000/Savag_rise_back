from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class DropCountdownBase(BaseModel):
    is_active: bool = True
    drop_name: str = Field(default="Savage Rise Drop", min_length=1, max_length=120)
    title: str = Field(default="Next drop", min_length=1, max_length=120)
    subtitle: Optional[str] = Field(default=None, max_length=240)
    launch_at: datetime
    cta_label: str = Field(default="Shop the drop", min_length=1, max_length=80)
    cta_url: str = Field(default="/products", min_length=1, max_length=300)
    email_enabled: bool = True
    email_subject: str = Field(default="Le nouveau drop Savage Rise est disponible", min_length=1, max_length=180)
    email_preview: Optional[str] = Field(default=None, max_length=300)

    @field_validator("launch_at")
    @classmethod
    def normalize_launch_at(cls, value: datetime) -> datetime:
        return _to_utc_naive(value)

    @field_validator("cta_url")
    @classmethod
    def validate_cta_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith("/") and not cleaned.startswith("http://") and not cleaned.startswith("https://"):
            raise ValueError("cta_url doit commencer par /, http:// ou https://")
        return cleaned


class DropCountdownUpdate(DropCountdownBase):
    pass


class DropCountdownOut(DropCountdownBase):
    seconds_remaining: int
    is_released: bool
    notification_sent_at: Optional[datetime] = None
    notification_recipients_count: int = 0
