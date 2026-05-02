"""WR2 FlowKit client — async HTTP wrapper around the FlowKit local agent.

FlowKit is a Python+Chrome-extension bridge that proxies image/video gen
calls through the user's logged-in `labs.google/fx/tools/flow` session. The
local agent serves on `http://127.0.0.1:8100` by default.

Empirically verified 2026-05-03 on Antonello's Ultra account:
- `GEM_PIX_2` (Nano Banana Pro) image generation is FREE for AI Ultra
  (`PAYGATE_TIER_TWO`) — 0 credit consumed across two consecutive images.
- Latency ~5-15s per image (vs ~30-90s through the WR2 Playwright path).

This module provides a thin, fail-soft client for use as a SECONDARY
backend in `scripts/wr2_image_generator.py`. When FlowKit is offline
(extension not loaded, server not running, token not captured) every
method that returns an `Optional` returns `None` so the caller can fall
back to the existing Playwright path.

Reference skill: ~/.claude/skills/nuzantara-flowkit-flow-generation.md
Reference memory: discovery_flowkit_poc_test_2026_05_03.md
"""
from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

import httpx

logger = logging.getLogger("wr2.flowkit_client")


# ─────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────


class FlowKitError(Exception):
    """Base exception for FlowKit client errors."""


class FlowKitGenerationError(FlowKitError):
    """Raised when /api/flow/generate-image returns non-2xx or malformed payload."""


class FlowKitDownloadError(FlowKitError):
    """Raised when fetching the signed CDN URL fails or yields zero bytes."""


class FlowKitProjectError(FlowKitError):
    """Raised when /api/projects fails to create or return a usable project_id."""


# ─────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────


class FlowKitClient:
    """Async HTTP client for the FlowKit local agent.

    Use as an async context manager so the underlying httpx.AsyncClient is
    created in `__aenter__` and closed in `__aexit__` (Golden Rule #10 —
    persistent client, never instantiated inside methods/loops).

    Example:
        async with FlowKitClient() as fk:
            if not await fk.is_available():
                return None  # caller falls back
            project_id = await fk.ensure_project("wr2-spt-2026-05")
            result = await fk.generate_image(
                project_id=project_id,
                prompt="Editorial photograph of ...",
                orientation="PORTRAIT",
            )
            await fk.download_image(result["fife_url"], dest_path)
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8100",
        timeout_s: float = 30.0,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = float(timeout_s)
        # `transport` lets tests inject httpx.MockTransport without monkeypatching.
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        # Cache the last project_id created via ensure_project(), keyed by
        # (name, material, language). Cheap O(1) avoids unnecessary POSTs
        # when generating multiple images in the same project.
        self._project_cache: dict[tuple[str, str, str], str] = {}

    # ── Context manager ──────────────────────────────────────────────────

    async def __aenter__(self) -> "FlowKitClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_s,
            transport=self._transport,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Internals ────────────────────────────────────────────────────────

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise FlowKitError(
                "FlowKitClient must be used as an async context manager",
            )
        return self._client

    # ── Public API ───────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any] | None:
        """GET /health — return the dict only if `extension_connected` is True.

        Returns:
            The full health JSON dict if the FlowKit server is up AND the
            Chrome extension is connected. None on any failure (server down,
            timeout, extension disconnected) so the caller can fall back.
        """
        client = self._require_client()
        try:
            resp = await client.get("/health")
        except (httpx.HTTPError, OSError) as e:
            logger.debug("FlowKit /health unreachable: %s", e)
            return None
        if resp.status_code != 200:
            logger.debug("FlowKit /health status=%d", resp.status_code)
            return None
        try:
            data = resp.json()
        except ValueError:
            logger.debug("FlowKit /health returned non-JSON")
            return None
        if not isinstance(data, dict):
            return None
        if not data.get("extension_connected"):
            logger.info("FlowKit extension not connected — falling back")
            return None
        return data

    async def get_credits(self) -> dict[str, Any] | None:
        """GET /api/flow/credits — return credits dict, or None on NO_FLOW_KEY.

        FlowKit returns `{"detail":"NO_FLOW_KEY"}` (with HTTP 401 or 200
        depending on version) when the bearer token has not yet been captured
        by the extension. We treat any failure as "fall back to Playwright"
        rather than raising.

        Returns:
            Dict with at minimum `credits`, `subscriptionCredits`,
            `topUpCredits`, `userPaygateTier`. None on any failure.
        """
        client = self._require_client()
        try:
            resp = await client.get("/api/flow/credits")
        except (httpx.HTTPError, OSError) as e:
            logger.debug("FlowKit /api/flow/credits unreachable: %s", e)
            return None
        if resp.status_code != 200:
            # 401, 5xx, etc. — most commonly NO_FLOW_KEY surfaced as 401.
            logger.info(
                "FlowKit /api/flow/credits status=%d (likely token not captured)",
                resp.status_code,
            )
            return None
        try:
            data = resp.json()
        except ValueError:
            logger.debug("FlowKit /api/flow/credits returned non-JSON")
            return None
        if not isinstance(data, dict):
            return None
        # Some FlowKit builds return 200 with a `detail` error envelope.
        detail = data.get("detail")
        if detail == "NO_FLOW_KEY":
            logger.info(
                "FlowKit token not captured (NO_FLOW_KEY) — falling back",
            )
            return None
        if "credits" not in data:
            logger.debug("FlowKit credits payload missing `credits` field: %r", data)
            return None
        return data

    async def is_available(self) -> bool:
        """Convenience: True iff health() AND get_credits() both succeed.

        Use this as the single gate before attempting generation. Avoids
        wasting time POSTing a generation request that will fail with
        NO_FLOW_KEY or extension-disconnected.
        """
        health = await self.health()
        if health is None:
            return False
        credits = await self.get_credits()
        if credits is None:
            return False
        return True

    async def ensure_project(
        self,
        name: str,
        material: str = "realistic",
        language: str = "en",
    ) -> str:
        """Create-or-return a FlowKit project_id for the given (name, material, language).

        FlowKit projects are namespaced containers for generation calls. The
        `material` field selects a built-in style preset (see skill doc:
        `realistic` is the default for editorial photo aesthetic). For
        Bali Zero WR2 hero slides we always want `realistic`.

        Cached in-process so generating N hero slides for the same dispatch
        doesn't POST N projects.

        Raises:
            FlowKitProjectError: on non-2xx response or missing `id` field.
        """
        client = self._require_client()
        cache_key = (name, material, language)
        cached = self._project_cache.get(cache_key)
        if cached:
            return cached
        body = {"name": name, "material": material, "language": language}
        try:
            resp = await client.post("/api/projects", json=body)
        except httpx.HTTPError as e:
            raise FlowKitProjectError(
                f"FlowKit /api/projects unreachable: {e}",
            ) from e
        if resp.status_code not in (200, 201):
            raise FlowKitProjectError(
                f"FlowKit /api/projects status={resp.status_code} body={resp.text[:200]}",
            )
        try:
            data = resp.json()
        except ValueError as e:
            raise FlowKitProjectError(
                f"FlowKit /api/projects returned non-JSON: {e}",
            ) from e
        # FlowKit response shape varies slightly by version; accept either
        # `id` or `project_id` at top level, or nested under `project`.
        project_id = (
            data.get("id")
            or data.get("project_id")
            or (data.get("project") or {}).get("id")
        )
        if not project_id or not isinstance(project_id, str):
            raise FlowKitProjectError(
                f"FlowKit /api/projects response missing project id: {data!r}",
            )
        self._project_cache[cache_key] = project_id
        return project_id

    async def generate_image(
        self,
        *,
        project_id: str,
        prompt: str,
        orientation: Literal["PORTRAIT", "LANDSCAPE"] = "PORTRAIT",
    ) -> dict[str, Any]:
        """POST /api/flow/generate-image — return parsed media metadata.

        Args:
            project_id: from ensure_project().
            prompt: full prompt text. Brand/anti-cliche modifiers should be
                applied by the caller — this client is intentionally
                modifier-unaware so it stays reusable for other Bali Zero
                surfaces (dispatch, marketing, etc.).
            orientation: PORTRAIT (4:5 / 9:16) or LANDSCAPE (16:9).

        Returns:
            Dict with keys:
                - media_id (str, UUID)
                - fife_url (str, signed CDN URL ~30 min TTL)
                - model (str, e.g. "GEM_PIX_2")
                - width, height (int)
                - seed (int)

        Raises:
            FlowKitGenerationError: on 4xx/5xx, malformed response, or
                missing required fields. Caller should catch and decide
                whether to retry or fall back.
        """
        client = self._require_client()
        body = {
            "project_id": project_id,
            "prompt": prompt,
            "orientation": orientation,
            "characters": [],
        }
        try:
            resp = await client.post("/api/flow/generate-image", json=body)
        except httpx.HTTPError as e:
            raise FlowKitGenerationError(
                f"FlowKit /api/flow/generate-image unreachable: {e}",
            ) from e
        if resp.status_code != 200:
            raise FlowKitGenerationError(
                f"FlowKit generate-image status={resp.status_code} "
                f"body={resp.text[:300]}",
            )
        try:
            data = resp.json()
        except ValueError as e:
            raise FlowKitGenerationError(
                f"FlowKit generate-image returned non-JSON: {e}",
            ) from e
        return _parse_image_response(data)

    async def download_image(
        self,
        fife_url: str,
        dest_path: Path,
    ) -> Path:
        """Async download a signed CDN URL to `dest_path`.

        Uses the same persistent httpx client (the CDN endpoint is on a
        different host but httpx handles the redirect/host swap fine).

        Raises:
            FlowKitDownloadError: on non-2xx response or zero-byte payload.
        """
        client = self._require_client()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # `follow_redirects=True` is required because the signed CDN URL
            # sometimes 302s through a Google-internal hop before serving.
            resp = await client.get(fife_url, follow_redirects=True)
        except httpx.HTTPError as e:
            raise FlowKitDownloadError(
                f"FlowKit CDN download unreachable: {e}",
            ) from e
        if resp.status_code != 200:
            raise FlowKitDownloadError(
                f"FlowKit CDN download status={resp.status_code}",
            )
        content = resp.content
        if not content:
            raise FlowKitDownloadError(
                "FlowKit CDN download returned zero bytes",
            )
        dest_path.write_bytes(content)
        # Defensive: write_bytes can succeed but produce empty file if
        # `content` was unexpectedly empty (already checked) or disk full.
        if dest_path.stat().st_size == 0:
            raise FlowKitDownloadError(
                f"FlowKit CDN download produced empty file at {dest_path}",
            )
        return dest_path


# ─────────────────────────────────────────────────────────────────────────
# Response parser (separate function for unit-testability)
# ─────────────────────────────────────────────────────────────────────────


def _parse_image_response(data: Any) -> dict[str, Any]:
    """Extract the canonical fields from a FlowKit generate-image response.

    The empirically-verified shape (see skill doc) is:

        {
          "media": [{
            "image": {
              "generatedImage": {
                "mediaId": "<uuid>",
                "fifeUrl": "https://flow-content.google/image/<id>?...",
                "modelNameType": "GEM_PIX_2",
                "seed": 784277,
                ...
              }
            },
            "dimensions": {"width": 768, "height": 1376}
          }],
          ...
        }

    Raises FlowKitGenerationError if the shape is unexpected or required
    fields are missing.
    """
    if not isinstance(data, dict):
        raise FlowKitGenerationError(
            f"generate-image response is not a dict: {type(data).__name__}",
        )
    media = data.get("media")
    if not isinstance(media, list) or not media:
        # Some FlowKit builds wrap errors as `{"detail": "..."}` with HTTP 200.
        detail = data.get("detail")
        if detail:
            raise FlowKitGenerationError(
                f"generate-image error detail={detail!r}",
            )
        raise FlowKitGenerationError(
            f"generate-image response has no `media` array: {data!r}",
        )
    first = media[0]
    if not isinstance(first, dict):
        raise FlowKitGenerationError(
            "generate-image media[0] is not a dict",
        )
    image_obj = (first.get("image") or {}).get("generatedImage") or {}
    media_id = image_obj.get("mediaId")
    fife_url = image_obj.get("fifeUrl")
    model = image_obj.get("modelNameType", "")
    seed = image_obj.get("seed", 0)
    dimensions = first.get("dimensions") or {}
    width = dimensions.get("width", 0)
    height = dimensions.get("height", 0)
    if not media_id or not isinstance(media_id, str):
        raise FlowKitGenerationError(
            f"generate-image response missing mediaId: {image_obj!r}",
        )
    if not fife_url or not isinstance(fife_url, str):
        raise FlowKitGenerationError(
            f"generate-image response missing fifeUrl: {image_obj!r}",
        )
    return {
        "media_id": media_id,
        "fife_url": fife_url,
        "model": str(model),
        "width": int(width or 0),
        "height": int(height or 0),
        "seed": int(seed or 0),
    }
