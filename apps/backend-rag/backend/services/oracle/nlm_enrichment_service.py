"""NLM Enrichment Service — async client for the NLM Bridge with HMAC signing.

Queries NotebookLM via the local bridge running on Pro Mac.
All failures (timeout, connection, HTTP errors) degrade gracefully to None,
ensuring the main RAG pipeline is never blocked by NLM unavailability.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from backend.utils.hmac_utils import sign_request

logger = logging.getLogger(__name__)


class NLMEnrichmentService:
    """Async HTTP client for the NLM Bridge with HMAC request signing."""

    def __init__(self, bridge_url: str, bridge_secret: str = "") -> None:
        self._bridge_url = bridge_url.rstrip("/")
        self._bridge_secret = bridge_secret
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a persistent async HTTP client, creating one if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def query(
        self,
        notebook_id: str,
        question: str,
        timeout: float = 10.0,
    ) -> dict[str, Any] | None:
        """Query the NLM bridge for enrichment data.

        Args:
            notebook_id: Target notebook identifier (e.g. "nb-immigration").
            question: The question to ask NotebookLM.
            timeout: Per-request timeout in seconds (overrides client default).

        Returns:
            Dict with ``answer`` and ``citations`` keys on success, or None on
            any failure (timeout, connection error, HTTP error, parse error).
        """
        payload = json.dumps(
            {"notebook_id": notebook_id, "question": question},
            separators=(",", ":"),
        )

        signature = sign_request(payload, self._bridge_secret)

        headers = {
            "Content-Type": "application/json",
            "X-Bridge-Signature": signature,
        }

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self._bridge_url}/nlm/query",
                content=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

        except httpx.TimeoutException:
            logger.warning(
                "NLM bridge timeout for notebook=%s (%.1fs)",
                notebook_id,
                timeout,
            )
            return None

        except httpx.ConnectError:
            logger.warning(
                "NLM bridge unreachable at %s",
                self._bridge_url,
            )
            return None

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "NLM bridge returned HTTP %d for notebook=%s",
                exc.response.status_code,
                notebook_id,
            )
            return None

        except Exception:
            logger.exception("Unexpected error querying NLM bridge")
            return None

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
