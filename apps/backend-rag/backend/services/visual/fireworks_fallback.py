"""Fireworks Flux.1 Dev fallback client for Visual Generator.

Used only when Imagen 4 fails all retries. Pattern originates from the
pre-WR2 fireworks MCP wrapper (WR1 tree, removed 2026-04-22); this
module is async/httpx + cost tracked.

Cost: ~$0.03/image, no tier difference.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FireworksError(RuntimeError):
    pass


@dataclass
class FireworksResult:
    ok: bool
    image_bytes: bytes | None = None
    mime_type: str = "image/jpeg"
    cost_usd: Decimal = Decimal("0")
    duration_ms: float = 0.0
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class FireworksClient:
    """Async Fireworks Flux.1 Dev client — safety fallback only."""

    API_URL = (
        "https://api.fireworks.ai/inference/v1/workflows"
        "/accounts/fireworks/models/flux-1-dev-fp8/text_to_image"
    )
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_COST = Decimal("0.03")

    def __init__(
        self,
        api_key: str | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
    ) -> None:
        resolved = api_key or os.environ.get("FIREWORKS_API_KEY")
        if not resolved:
            raise FireworksError(
                "FireworksClient requires FIREWORKS_API_KEY",
            )
        self.api_key = resolved
        self._client = http_client
        self.timeout = timeout or self.DEFAULT_TIMEOUT

    async def generate(
        self,
        prompt: str,
        *,
        width: int = 1440,
        height: int = 1800,
        negative_prompt: str | None = None,
    ) -> FireworksResult:
        start = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "image/jpeg",
        }
        payload: dict[str, Any] = {
            "prompt": prompt,
            "width": width,
            "height": height,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        client = self._client
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout)
            close_client = True

        try:
            resp = await client.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            duration_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return FireworksResult(
                    ok=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                    duration_ms=duration_ms,
                )

            content_type = resp.headers.get("content-type", "").lower()
            if "image" in content_type:
                return FireworksResult(
                    ok=True,
                    image_bytes=resp.content,
                    mime_type=content_type,
                    cost_usd=self.DEFAULT_COST,
                    duration_ms=duration_ms,
                )
            # Some responses return JSON with base64
            try:
                body = resp.json()
                b64 = body.get("image") or body.get("data") or ""
                if b64:
                    return FireworksResult(
                        ok=True,
                        image_bytes=base64.b64decode(b64),
                        cost_usd=self.DEFAULT_COST,
                        duration_ms=duration_ms,
                    )
            except ValueError:
                pass
            return FireworksResult(
                ok=False,
                error=f"unexpected response content-type={content_type}",
                duration_ms=duration_ms,
            )
        except Exception as exc:  # noqa: BLE001
            return FireworksResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        finally:
            if close_client:
                await client.aclose()
