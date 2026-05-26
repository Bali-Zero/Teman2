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


# Golden Rule #10: module-level lazy singleton AsyncClient. Lifespan
# closes via close_ig_publisher_client() in app_factory.lifespan().
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_ig_publisher_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


async def validate_ig_credentials_at_startup(*, raise_on_failure: bool = False) -> dict[str, object]:
    """Verify IG Graph credentials at app startup.

    WR2 autonomous workflow Phase 1.5 — Codex amendment.
    Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §8.1

    Discovers IG_USER_ID / IG_LONG_LIVED_TOKEN (primary) with fallback to
    INSTAGRAM_ACCOUNT_ID / INSTAGRAM_ACCESS_TOKEN (existing convention).
    Validates: (1) both aliases consistent if both present (fail-loud on
    mismatch); (2) Meta Graph `/me` returns 200 with matching account_id.
    Logs ONLY account_id + username (NEVER token).

    Returns dict with `status` ('ok' | 'mismatch' | 'invalid_token' |
    'missing'), `account_id`, `username`, `source` (which env var pair won).

    Set `raise_on_failure=True` to abort startup; default returns the dict
    so callers (service_initializer) can decide.
    """
    ig_id = os.environ.get("IG_USER_ID")
    ig_tok = os.environ.get("IG_LONG_LIVED_TOKEN")
    insta_id = os.environ.get("INSTAGRAM_ACCOUNT_ID")
    insta_tok = os.environ.get("INSTAGRAM_ACCESS_TOKEN")

    if ig_id and insta_id and ig_id != insta_id:
        msg = (
            f"IG account mismatch: IG_USER_ID={ig_id} vs "
            f"INSTAGRAM_ACCOUNT_ID={insta_id}. Spec §8.1 requires consistent aliases."
        )
        logger.error(msg)
        if raise_on_failure:
            raise PublisherError(msg)
        return {"status": "mismatch", "account_id": None, "username": None, "source": None}

    primary_id = ig_id or insta_id
    primary_tok = ig_tok or insta_tok
    source = (
        "IG_USER_ID+IG_LONG_LIVED_TOKEN"
        if (ig_id and ig_tok)
        else "INSTAGRAM_ACCOUNT_ID+INSTAGRAM_ACCESS_TOKEN"
        if (insta_id and insta_tok)
        else None
    )

    if not primary_id or not primary_tok:
        msg = (
            "IG credentials missing: need IG_USER_ID + IG_LONG_LIVED_TOKEN "
            "(or INSTAGRAM_ACCOUNT_ID + INSTAGRAM_ACCESS_TOKEN as fallback)"
        )
        logger.warning(msg)
        if raise_on_failure:
            raise PublisherError(msg)
        return {"status": "missing", "account_id": None, "username": None, "source": None}

    if ig_id and insta_id:
        logger.warning(
            "IG credentials: both IG_* and INSTAGRAM_* aliases present, using IG_* (primary). "
            "Spec §8.1 recommends canonicalizing to IG_USER_ID/IG_LONG_LIVED_TOKEN.",
        )

    client = _get_module_client(DEFAULT_TIMEOUT)
    try:
        resp = await client.get(
            f"{DEFAULT_GRAPH_BASE}/{primary_id}",
            params={"access_token": primary_tok, "fields": "id,username"},
        )
    except httpx.HTTPError as exc:
        msg = f"IG credentials: Meta Graph unreachable ({type(exc).__name__}: {exc})"
        logger.warning(msg)
        if raise_on_failure:
            raise PublisherError(msg) from exc
        return {"status": "invalid_token", "account_id": primary_id, "username": None, "source": source}

    if resp.status_code != 200:
        msg = (
            f"IG credentials: Meta Graph returned {resp.status_code} for account_id={primary_id} "
            f"(token may be expired or revoked)"
        )
        logger.error(msg)
        if raise_on_failure:
            raise PublisherError(msg)
        return {"status": "invalid_token", "account_id": primary_id, "username": None, "source": source}

    data = resp.json()
    verified_id = str(data.get("id", ""))
    username = data.get("username")

    if verified_id and verified_id != str(primary_id):
        msg = (
            f"IG credentials: account_id mismatch — env={primary_id} vs graph={verified_id}"
        )
        logger.error(msg)
        if raise_on_failure:
            raise PublisherError(msg)
        return {"status": "mismatch", "account_id": verified_id, "username": username, "source": source}

    logger.info(
        f"IG credentials validated: account_id={verified_id} username={username or '?'} source={source}",
    )
    return {"status": "ok", "account_id": verified_id, "username": username, "source": source}


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
            issues.append(f"carousel has {len(draft.slides) + 1} items, max 10")
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

        client = self._client or _get_module_client(self.timeout)

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
        except Exception as exc:
            return PublishResult(
                ok=False,
                platform=Platform.INSTAGRAM,
                draft_id=draft.draft_id,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def delete(self, post_external_id: str) -> bool:
        """Meta Graph API supports DELETE /{media-id}; best-effort."""
        client = self._client or _get_module_client(self.timeout)
        try:
            resp = await client.delete(
                f"{self.graph_base}/{post_external_id}",
                params={"access_token": self.access_token},
                timeout=self.timeout,
            )
            return resp.status_code in (200, 204)
        except Exception as exc:
            logger.info("ig delete failed: %s", exc)
            return False

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
        except Exception:
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
            "IG API returned %s: %s",
            resp.status_code,
            resp.text[:300],
        )
        return None
    try:
        body = resp.json()
    except ValueError:
        logger.warning("IG API non-json response: %s", resp.text[:300])
        return None
    mid = body.get("id")
    return str(mid) if mid else None
