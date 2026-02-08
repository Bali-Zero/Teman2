"""
Base class for async HTTP services (messaging integrations).

Extracted from the repeated pattern in:
- WhatsAppService (whatsapp_service.py)
- InstagramService (instagram_service.py)
- TelegramBotService (telegram_bot_service.py)

All three share identical _get_client(), close(), and HTTP error handling patterns.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.app.core.constants import HttpTimeoutConstants

logger = logging.getLogger(__name__)


class AsyncHttpService:
    """
    Base class for services that make async HTTP calls via httpx.

    Provides:
    - Lazy singleton httpx.AsyncClient with configurable timeout
    - Graceful close
    - Standard error handling for HTTP responses
    - JSON response parsing with error extraction

    Subclasses implement:
    - service_name: str property for logging
    - Any API-specific methods
    """

    def __init__(self, timeout: float | None = None) -> None:
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout or HttpTimeoutConstants.EXTERNAL_API_TIMEOUT

    @property
    def service_name(self) -> str:
        """Override in subclass for logging context."""
        return self.__class__.__name__

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client (lazy singleton)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client gracefully."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        POST JSON payload and return parsed response.

        Raises:
            ValueError: If API returns an error response
            httpx.HTTPError: If connection fails
        """
        client = await self._get_client()
        try:
            response = await client.post(url, headers=headers, json=payload)
            result: dict[str, Any] = response.json()

            if response.status_code != 200:
                error_data = result.get("error", {})
                error_msg = error_data.get("message", "Unknown error")
                error_code = error_data.get("code", response.status_code)
                logger.error(f"{self.service_name} API error [{error_code}]: {error_msg}")
                raise ValueError(f"{self.service_name} API error [{error_code}]: {error_msg}")

            return result

        except httpx.HTTPError as e:
            logger.error(f"{self.service_name} HTTP error: {e}")
            raise

    async def _get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        GET with query params and return parsed JSON response.

        Raises:
            ValueError: If API returns an error response
            httpx.HTTPError: If connection fails
        """
        client = await self._get_client()
        try:
            response = await client.get(url, params=params, headers=headers)
            result: dict[str, Any] = response.json()

            if response.status_code != 200:
                error_data = result.get("error", {})
                error_msg = error_data.get("message", "Unknown error")
                logger.error(f"{self.service_name} API error: {error_msg}")
                raise ValueError(f"{self.service_name} API error: {error_msg}")

            return result

        except httpx.HTTPError as e:
            logger.error(f"{self.service_name} HTTP error: {e}")
            raise

    def _auth_header(self, token: str) -> dict[str, str]:
        """Build standard Bearer auth header."""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
