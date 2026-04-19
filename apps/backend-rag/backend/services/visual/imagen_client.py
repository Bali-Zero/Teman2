"""Imagen 4 client — Google Gen AI REST (image gen, not LLM → Law 1 not violated).

Routes:
- ImagenQuality.ULTRA  → imagen-4.0-ultra-generate-001   ($0.06/image, hero/cover)
- ImagenQuality.FAST   → imagen-4.0-fast-generate-001    ($0.02/image, body slides)
- ImagenQuality.STANDARD → imagen-4.0-generate-001       ($0.04/image, optional)

Uses Gemini API endpoint with :predict action. Requires GOOGLE_API_KEY or
GEMINI_API_KEY env var. Async via httpx.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

import httpx

from backend.services.observability import llm_cost_tracked, set_usage

logger = logging.getLogger(__name__)


class ImagenError(RuntimeError):
    """Raised on configuration errors (missing key); per-call errors surface in ImagenResult."""


class ImagenQuality(str, Enum):
    ULTRA = "ultra"
    STANDARD = "standard"
    FAST = "fast"

    @property
    def model_id(self) -> str:
        return _MODEL_IDS[self]

    @property
    def cost_usd(self) -> Decimal:
        return _COSTS[self]


_MODEL_IDS: dict[ImagenQuality, str] = {
    ImagenQuality.ULTRA: "imagen-4.0-ultra-generate-001",
    ImagenQuality.STANDARD: "imagen-4.0-generate-001",
    ImagenQuality.FAST: "imagen-4.0-fast-generate-001",
}

_COSTS: dict[ImagenQuality, Decimal] = {
    ImagenQuality.ULTRA: Decimal("0.06"),
    ImagenQuality.STANDARD: Decimal("0.04"),
    ImagenQuality.FAST: Decimal("0.02"),
}


@dataclass
class ImagenResult:
    ok: bool
    quality: ImagenQuality
    model_id: str
    image_bytes: bytes | None = None
    mime_type: str = "image/png"
    error: str | None = None
    cost_usd: Decimal = Decimal("0")
    duration_ms: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def size_bytes(self) -> int:
        return len(self.image_bytes) if self.image_bytes else 0


class ImagenClient:
    """Async Imagen 4 client targeting Google's Gemini API /predict endpoint.

    The endpoint (as of 2026-04) returns base64-encoded image bytes inside
    ``predictions[0].bytesBase64Encoded``. If the contract changes, adjust
    ``_parse_response`` — everything else stays.

    Parameters
    ----------
    api_key : str
        Google API key with Gemini access.
    aspect_ratio : str
        Default "3:4" (portrait — IG carousel renders it fine with optional
        centre crop to 4:5 if pixel-perfect parity is required). "16:9" for
        X hero, "1:1" for avatars, "9:16" for IG stories / reels.

        NOTE: Imagen 4.0 API rejects "4:5" with HTTP 400. Supported set:
        1:1, 9:16, 16:9, 4:3, 3:4. Do not default to 4:5 even if the IG
        spec wants it — crop client-side in VisualGenerator if needed.
    http_client : httpx.AsyncClient, optional
        Injected client for tests; created per-call otherwise.
    base_url : str
        Defaults to public Gemini endpoint.
    """

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    DEFAULT_TIMEOUT = 60.0
    SUPPORTED_ASPECT_RATIOS = frozenset({"1:1", "9:16", "16:9", "4:3", "3:4"})

    def __init__(
        self,
        api_key: str | None = None,
        *,
        aspect_ratio: str = "3:4",
        http_client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        resolved_key = (
            api_key
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )
        if not resolved_key:
            raise ImagenError(
                "ImagenClient requires GOOGLE_API_KEY or GEMINI_API_KEY",
            )
        self.api_key = resolved_key
        if aspect_ratio not in self.SUPPORTED_ASPECT_RATIOS:
            raise ImagenError(
                f"aspect_ratio {aspect_ratio!r} is not supported by Imagen 4.0. "
                f"Supported: {sorted(self.SUPPORTED_ASPECT_RATIOS)}",
            )
        self.aspect_ratio = aspect_ratio
        self._client = http_client
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._last_model: str = "imagen-4.0-fast-generate-001"

    @llm_cost_tracked(provider="imagen", model_attr="_last_model")
    async def generate(
        self,
        prompt: str,
        *,
        quality: ImagenQuality = ImagenQuality.FAST,
        negative_prompt: str | None = None,
        aspect_ratio: str | None = None,
    ) -> ImagenResult:
        self._last_model = quality.model_id
        set_usage(input_tokens=1, output_tokens=0)
        start = time.perf_counter()
        model_id = quality.model_id
        url = f"{self.base_url}/{model_id}:predict?key={self.api_key}"

        effective_aspect = aspect_ratio or self.aspect_ratio
        if effective_aspect not in self.SUPPORTED_ASPECT_RATIOS:
            return ImagenResult(
                ok=False,
                quality=quality,
                model_id=model_id,
                error=(
                    f"aspect_ratio {effective_aspect!r} not supported by "
                    f"Imagen 4.0 (supported: "
                    f"{sorted(self.SUPPORTED_ASPECT_RATIOS)})"
                ),
                duration_ms=0.0,
            )

        instance: dict[str, Any] = {"prompt": prompt}
        if negative_prompt:
            instance["negativePrompt"] = negative_prompt

        params: dict[str, Any] = {
            "sampleCount": 1,
            "aspectRatio": effective_aspect,
        }
        payload = {"instances": [instance], "parameters": params}

        client = self._client
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout)
            close_client = True

        try:
            resp = await client.post(url, json=payload, timeout=self.timeout)
            duration_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return ImagenResult(
                    ok=False,
                    quality=quality,
                    model_id=model_id,
                    error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                    duration_ms=duration_ms,
                )

            body = resp.json()
            image_bytes, mime_type, err = _parse_response(body)
            if err:
                return ImagenResult(
                    ok=False,
                    quality=quality,
                    model_id=model_id,
                    error=err,
                    duration_ms=duration_ms,
                    meta={"body_keys": list(body.keys())},
                )
            return ImagenResult(
                ok=True,
                quality=quality,
                model_id=model_id,
                image_bytes=image_bytes,
                mime_type=mime_type,
                cost_usd=quality.cost_usd,
                duration_ms=duration_ms,
            )
        except Exception as exc:  # noqa: BLE001
            return ImagenResult(
                ok=False,
                quality=quality,
                model_id=model_id,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        finally:
            if close_client:
                await client.aclose()


def _parse_response(
    body: dict[str, Any],
) -> tuple[bytes | None, str, str | None]:
    """Extract base64 image bytes from the Imagen 4 response body.

    Expected shape:
        { "predictions": [ { "bytesBase64Encoded": "...", "mimeType": "image/png" } ] }

    Falls back to "image/jpeg" if mimeType is missing. Returns (bytes, mime, err).
    """
    preds = body.get("predictions")
    if not preds or not isinstance(preds, list):
        return None, "", "response missing 'predictions' array"
    first = preds[0]
    if not isinstance(first, dict):
        return None, "", "predictions[0] is not a dict"
    b64 = first.get("bytesBase64Encoded") or first.get("imageBytes")
    if not b64:
        # Some Imagen responses use 'image.bytes' nested
        inner = first.get("image")
        if isinstance(inner, dict):
            b64 = inner.get("bytesBase64Encoded")
    if not b64:
        return None, "", "no base64 image bytes found in response"
    try:
        raw = base64.b64decode(b64)
    except Exception as exc:  # noqa: BLE001
        return None, "", f"base64 decode failed: {exc}"
    mime = first.get("mimeType") or "image/png"
    return raw, mime, None
