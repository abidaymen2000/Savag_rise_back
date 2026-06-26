import asyncio
import logging

import httpx

from app.config import settings


logger = logging.getLogger("meta.client")


class MetaRetryableError(Exception):
    def __init__(self, message: str, *, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class MetaPermanentError(Exception):
    pass


class MetaDisabledError(Exception):
    pass


class MetaConversionsApiClient:
    def __init__(self, *, timeout_seconds: float = 5.0, max_retries: int = 0):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def _endpoint(self) -> str:
        pixel_id = settings.META_PIXEL_ID
        token = settings.META_CONVERSIONS_API_TOKEN
        if not settings.META_CAPI_ENABLED or not pixel_id or token is None:
            raise MetaDisabledError("Meta Conversions API disabled")
        return f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/{pixel_id}/events"

    async def send_events(self, payload: dict) -> dict:
        endpoint = self._endpoint()
        token = settings.META_CONVERSIONS_API_TOKEN
        assert token is not None
        headers = {"Authorization": f"Bearer {token.get_secret_value()}"}
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                if attempt >= self.max_retries:
                    raise MetaRetryableError("Meta timeout") from exc
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            except httpx.NetworkError as exc:
                if attempt >= self.max_retries:
                    raise MetaRetryableError("Meta network error") from exc
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                retry_after_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
                raise MetaRetryableError("Meta rate limit", retry_after_seconds=retry_after_seconds)
            if response.status_code in {401, 403}:
                raise MetaPermanentError(f"Meta authentication/configuration error ({response.status_code})")
            if response.status_code >= 500:
                if attempt >= self.max_retries:
                    raise MetaRetryableError(f"Meta returned {response.status_code}")
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code >= 400:
                logger.warning("Meta rejected event with status=%s", response.status_code)
                raise MetaPermanentError(f"Meta validation error ({response.status_code})")
            return response.json()
        raise MetaRetryableError("Meta request failed")
