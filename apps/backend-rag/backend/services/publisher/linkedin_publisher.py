"""LinkedIn Publisher — REST Posts API v2.

Flow (LinkedIn REST API v202507+):
    1. POST /rest/posts
       body: { author, commentary, visibility, distribution, content? }
    2. If image attached: we use the shareMedia-in-post pattern by
       supplying `content.article.source` (external URL) — avoids the
       extra image-asset upload step. Fine for Tigris-hosted assets.

Auth: OAuth2 bearer via env ``LINKEDIN_ACCESS_TOKEN`` + author URN via
``LINKEDIN_AUTHOR_URN`` (e.g. ``urn:li:person:xxxx`` or
``urn:li:organization:xxxx``).

Design §9.4. Sprint 8.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from backend.services.publisher.base import (
    DraftPayload,
    Publisher,
    PublisherError,
    PublishResult,
    ValidationResult,
)
from backend.services.war_room.models import Platform

logger = logging.getLogger(__name__)


DEFAULT_API_BASE = "https://api.linkedin.com/rest"
DEFAULT_TIMEOUT = 25.0
LINKEDIN_API_VERSION = "202507"
MAX_COMMENTARY_CHARS = 3000


# Golden Rule #10: module-level lazy singleton AsyncClient.
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client  # noqa: PLW0603 — singleton by design
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_linkedin_publisher_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client  # noqa: PLW0603
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


class LinkedInPublisher(Publisher):
    platform_name = Platform.LINKEDIN

    def __init__(
        self,
        *,
        access_token: str | None = None,
        author_urn: str | None = None,
        api_base: str | None = None,
        api_version: str = LINKEDIN_API_VERSION,
        http_client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
    ) -> None:
        self.access_token = (
            access_token or os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
        )
        self.author_urn = (
            author_urn or os.environ.get("LINKEDIN_AUTHOR_URN", "")
        )
        if not self.access_token or not self.author_urn:
            raise PublisherError(
                "LinkedInPublisher requires LINKEDIN_ACCESS_TOKEN + "
                "LINKEDIN_AUTHOR_URN (urn:li:person:... or urn:li:organization:...)",
            )
        if not self.author_urn.startswith("urn:li:"):
            raise PublisherError(
                f"invalid author URN format: {self.author_urn!r}",
            )
        self.api_base = (api_base or DEFAULT_API_BASE).rstrip("/")
        self.api_version = api_version
        self._client = http_client
        self.timeout = timeout or DEFAULT_TIMEOUT

    # ── Public API ───────────────────────────────────────────────────

    async def validate(self, draft: DraftPayload) -> ValidationResult:
        issues: list[str] = []
        if not draft.main_caption or not draft.main_caption.strip():
            issues.append("main_caption required")
        if len(draft.main_caption or "") > MAX_COMMENTARY_CHARS:
            issues.append(
                f"commentary exceeds {MAX_COMMENTARY_CHARS} chars",
            )
        return ValidationResult(
            ok=not issues,
            platform=Platform.LINKEDIN,
            issues=issues,
        )

    async def publish(self, draft: DraftPayload) -> PublishResult:
        validation = await self.validate(draft)
        if not validation.ok:
            return PublishResult(
                ok=False,
                platform=Platform.LINKEDIN,
                draft_id=draft.draft_id,
                error=f"validation: {', '.join(validation.issues)}",
            )

        client = self._client or _get_module_client(self.timeout)

        try:
            body = self._build_post_body(draft)
            resp = await client.post(
                f"{self.api_base}/posts",
                headers=self._headers(),
                json=body,
                timeout=self.timeout,
            )
            # LinkedIn returns 201 Created with x-restli-id header containing the URN
            if resp.status_code not in (200, 201):
                return PublishResult(
                    ok=False,
                    platform=Platform.LINKEDIN,
                    draft_id=draft.draft_id,
                    error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                )
            urn = (
                resp.headers.get("x-restli-id")
                or resp.headers.get("x-linkedin-id")
                or ""
            )
            if not urn:
                # fall back to response body
                try:
                    urn = (resp.json() or {}).get("id", "")
                except ValueError:
                    urn = ""
            if not urn:
                return PublishResult(
                    ok=False,
                    platform=Platform.LINKEDIN,
                    draft_id=draft.draft_id,
                    error="no post URN returned by API",
                )
            return PublishResult(
                ok=True,
                platform=Platform.LINKEDIN,
                draft_id=draft.draft_id,
                post_external_id=urn,
                post_url=_urn_to_url(urn),
                final_text=draft.main_caption,
                meta={"urn": urn, "author": self.author_urn},
            )
        except Exception as exc:  # noqa: BLE001
            return PublishResult(
                ok=False,
                platform=Platform.LINKEDIN,
                draft_id=draft.draft_id,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def delete(self, post_external_id: str) -> bool:
        client = self._client or _get_module_client(self.timeout)
        try:
            resp = await client.delete(
                f"{self.api_base}/posts/{post_external_id}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            return resp.status_code in (200, 204)
        except Exception as exc:  # noqa: BLE001
            logger.info("linkedin delete failed: %s", exc)
            return False

    # ── Internal ─────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": self.api_version,
        }

    def _build_post_body(self, draft: DraftPayload) -> dict[str, Any]:
        body: dict[str, Any] = {
            "author": self.author_urn,
            "commentary": draft.main_caption,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if draft.cover_image_url and draft.link_url:
            body["content"] = {
                "article": {
                    "source": draft.link_url,
                    "thumbnail": draft.cover_image_url,
                    "title": draft.topic[:200],
                    "description": (
                        draft.main_caption[:255]
                        if draft.main_caption
                        else None
                    ),
                }
            }
        return body


def _urn_to_url(urn: str) -> str | None:
    # URNs look like ``urn:li:share:7194...`` or ``urn:li:ugcPost:...``.
    # LinkedIn web URLs are /feed/update/urn:li:share:XXX/ — percent-encoded.
    if not urn.startswith("urn:li:"):
        return None
    from urllib.parse import quote

    return f"https://www.linkedin.com/feed/update/{quote(urn, safe='')}/"
