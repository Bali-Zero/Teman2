"""Instagram Graph API Publisher — carousel via image_url uploads.

Flow (Meta Graph API v20):
    1. For each slide i: POST /{IG_USER_ID}/media
       params: image_url, is_carousel_item=true → returns container id
    2. POST /{IG_USER_ID}/media
       params: caption, media_type=CAROUSEL, children=c1,c2,... → returns
       parent container id
    3. POST /{IG_USER_ID}/media_publish
       params: creation_id=parent_id → returns the final media id
    4. Optional: GET /{id}?fields=permalink → post_url

Requires env:
    IG_USER_ID         — numeric business account id
    IG_LONG_LIVED_TOKEN — 60-day long-lived access token

Note: Meta uses pagination/throttling; we keep the flow simple and rely on
a single attempt per container. Orchestrator handles retries.
"""

from __future__ import annotations

import logging
import os

import httpx

from backend.services.publisher.base import (
    DraftPayload,
    Publisher,
    PublisherError,
    PublishResult,
    SlidePayload,
    ValidationResult,
)
from backend.services.war_room.models import Platform

logger = logging.getLogger(__name__)


DEFAULT_GRAPH_BASE = "https://graph.facebook.com/v20.0"
DEFAULT_TIMEOUT = 30.0


class IGPublisher(Publisher):
    platform_name = Platform.INSTAGRAM

    def __init__(
        self,
        *,
        ig_user_id: str | None = None,
        access_token: str | None = None,
        graph_base: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
    ) -> None:
        self.ig_user_id = (
            ig_user_id
            or os.environ.get("IG_USER_ID")
            or os.environ.get("INSTAGRAM_ACCOUNT_ID")
            or ""
        )
        self.access_token = (
            access_token
            or os.environ.get("IG_LONG_LIVED_TOKEN")
            or os.environ.get("INSTAGRAM_ACCESS_TOKEN")
            or ""
        )
        if not self.ig_user_id or not self.access_token:
            raise PublisherError(
                "IGPublisher requires IG_USER_ID (or INSTAGRAM_ACCOUNT_ID) "
                "and IG_LONG_LIVED_TOKEN (or INSTAGRAM_ACCESS_TOKEN)",
            )
        self.graph_base = (graph_base or DEFAULT_GRAPH_BASE).rstrip("/")
        self._client = http_client
        self.timeout = timeout or DEFAULT_TIMEOUT

    # ── Public API ───────────────────────────────────────────────────

    async def validate(self, draft: DraftPayload) -> ValidationResult:
        issues: list[str] = []
        if not draft.cover_image_url:
            issues.append("cover_image_url is required")
        if not draft.slides and not draft.cover_image_url:
            issues.append("draft has no slides and no cover")
        if len(draft.slides) + 1 > 10:
            # IG carousel max 10 items (including cover)
            issues.append(f"carousel has {len(draft.slides)+1} items, max 10")
        caption = draft.main_caption or ""
        if len(caption) > 2200:
            issues.append(f"caption exceeds 2200 chars ({len(caption)})")
        return ValidationResult(
            ok=not issues,
            platform=Platform.INSTAGRAM,
            issues=issues,
        )

    async def publish(self, draft: DraftPayload) -> PublishResult:
        validation = await self.validate(draft)
        if not validation.ok:
            return PublishResult(
                ok=False,
                platform=Platform.INSTAGRAM,
                draft_id=draft.draft_id,
                error=f"validation: {', '.join(validation.issues)}",
            )

        client = self._client
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout)
            close_client = True

        try:
            items = _build_items(draft)
            container_ids: list[str] = []

            for slide in items:
                container = await self._create_child_container(client, slide)
                if not container:
                    return PublishResult(
                        ok=False,
                        platform=Platform.INSTAGRAM,
                        draft_id=draft.draft_id,
                        error=f"create_child failed for slide {slide.slide_number}",
                    )
                container_ids.append(container)

            parent_id = await self._create_parent_container(
                client,
                caption=draft.main_caption,
                children_ids=container_ids,
            )
            if not parent_id:
                return PublishResult(
                    ok=False,
                    platform=Platform.INSTAGRAM,
                    draft_id=draft.draft_id,
                    error="create_parent failed",
                )

            media_id = await self._publish_parent(client, parent_id)
            if not media_id:
                return PublishResult(
                    ok=False,
                    platform=Platform.INSTAGRAM,
                    draft_id=draft.draft_id,
                    error="media_publish failed",
                )

            permalink = await self._fetch_permalink(client, media_id)
            return PublishResult(
                ok=True,
                platform=Platform.INSTAGRAM,
                draft_id=draft.draft_id,
                post_external_id=media_id,
                post_url=permalink,
                final_text=draft.main_caption,
                meta={
                    "carousel_items": len(container_ids),
                    "parent_id": parent_id,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return PublishResult(
                ok=False,
                platform=Platform.INSTAGRAM,
                draft_id=draft.draft_id,
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            if close_client:
                await client.aclose()

    async def delete(self, post_external_id: str) -> bool:
        """Meta Graph API supports DELETE /{media-id}; best-effort."""
        client = self._client
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout)
            close_client = True
        try:
            resp = await client.delete(
                f"{self.graph_base}/{post_external_id}",
                params={"access_token": self.access_token},
                timeout=self.timeout,
            )
            return resp.status_code in (200, 204)
        except Exception as exc:  # noqa: BLE001
            logger.info("ig delete failed: %s", exc)
            return False
        finally:
            if close_client:
                await client.aclose()

    # ── Internal ─────────────────────────────────────────────────────

    async def _create_child_container(
        self,
        client: httpx.AsyncClient,
        slide: SlidePayload,
    ) -> str | None:
        params = {
            "image_url": slide.image_url,
            "is_carousel_item": "true",
            "access_token": self.access_token,
        }
        resp = await client.post(
            f"{self.graph_base}/{self.ig_user_id}/media",
            params=params,
            timeout=self.timeout,
        )
        return _parse_id(resp)

    async def _create_parent_container(
        self,
        client: httpx.AsyncClient,
        *,
        caption: str,
        children_ids: list[str],
    ) -> str | None:
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
            "access_token": self.access_token,
        }
        resp = await client.post(
            f"{self.graph_base}/{self.ig_user_id}/media",
            params=params,
            timeout=self.timeout,
        )
        return _parse_id(resp)

    async def _publish_parent(
        self,
        client: httpx.AsyncClient,
        parent_id: str,
    ) -> str | None:
        params = {
            "creation_id": parent_id,
            "access_token": self.access_token,
        }
        resp = await client.post(
            f"{self.graph_base}/{self.ig_user_id}/media_publish",
            params=params,
            timeout=self.timeout,
        )
        return _parse_id(resp)

    async def _fetch_permalink(
        self,
        client: httpx.AsyncClient,
        media_id: str,
    ) -> str | None:
        try:
            resp = await client.get(
                f"{self.graph_base}/{media_id}",
                params={
                    "fields": "permalink",
                    "access_token": self.access_token,
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return None
            body = resp.json()
            return body.get("permalink")
        except Exception:  # noqa: BLE001 — permalink is optional
            return None


# ── helpers ──────────────────────────────────────────────────────────


def _build_items(draft: DraftPayload) -> list[SlidePayload]:
    items: list[SlidePayload] = []
    # cover first
    items.append(
        SlidePayload(
            slide_number=1,
            image_url=draft.cover_image_url,
            caption=None,
        )
    )
    # body slides (preserve caller's order)
    for slide in draft.slides:
        items.append(slide)
    return items


def _parse_id(resp: httpx.Response) -> str | None:
    if resp.status_code != 200:
        logger.warning(
            "IG API returned %s: %s", resp.status_code, resp.text[:300],
        )
        return None
    try:
        body = resp.json()
    except ValueError:
        logger.warning("IG API non-json response: %s", resp.text[:300])
        return None
    mid = body.get("id")
    return str(mid) if mid else None
