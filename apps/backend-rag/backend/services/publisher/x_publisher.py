"""X (Twitter) Publisher — API v2 threaded tweets.

Flow:
    1. Post first tweet: main_caption + optional cover media
    2. For each subsequent slide: post with ``in_reply_to.in_reply_to_tweet_id``
       referencing the parent (X v2 field `reply.in_reply_to_tweet_id`)
    3. Media upload optional (v2 ``/2/media/upload``); for v1 we rely on
       Tigris-hosted image URLs embedded in tweet text (X ingests them as
       cards). Keeping media upload as a future extension when we have OAuth
       1.0a user context working.

Tweet text cap: 280 chars. We truncate with an ellipsis on overflow so the
publisher never raises.

Auth: OAuth 2.0 user-context bearer token via env ``X_BEARER_TOKEN``.
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


DEFAULT_API_BASE = "https://api.twitter.com/2"
DEFAULT_TIMEOUT = 20.0
MAX_TWEET_CHARS = 280


# Golden Rule #10: module-level lazy singleton AsyncClient.
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client  # noqa: PLW0603 — singleton by design
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_x_publisher_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client  # noqa: PLW0603
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


class XPublisher(Publisher):
    platform_name = Platform.X

    def __init__(
        self,
        *,
        bearer_token: str | None = None,
        api_base: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
    ) -> None:
        self.bearer_token = (
            bearer_token or os.environ.get("X_BEARER_TOKEN", "")
        )
        if not self.bearer_token:
            raise PublisherError(
                "XPublisher requires X_BEARER_TOKEN",
            )
        self.api_base = (api_base or DEFAULT_API_BASE).rstrip("/")
        self._client = http_client
        self.timeout = timeout or DEFAULT_TIMEOUT

    # ── Public API ───────────────────────────────────────────────────

    async def validate(self, draft: DraftPayload) -> ValidationResult:
        issues: list[str] = []
        if not draft.main_caption or not draft.main_caption.strip():
            issues.append("main_caption required")
        total_frames = 1 + len(draft.slides)
        if total_frames > 25:
            issues.append(f"thread too long: {total_frames} > 25")
        return ValidationResult(
            ok=not issues,
            platform=Platform.X,
            issues=issues,
        )

    async def publish(self, draft: DraftPayload) -> PublishResult:
        validation = await self.validate(draft)
        if not validation.ok:
            return PublishResult(
                ok=False,
                platform=Platform.X,
                draft_id=draft.draft_id,
                error=f"validation: {', '.join(validation.issues)}",
            )

        client = self._client or _get_module_client(self.timeout)

        try:
            tweets = _build_thread(draft)

            # first tweet
            first_id = await self._post_tweet(
                client, text=tweets[0], reply_to=None,
            )
            if not first_id:
                return PublishResult(
                    ok=False,
                    platform=Platform.X,
                    draft_id=draft.draft_id,
                    error="first tweet failed",
                )

            # chained replies
            posted: list[str] = [first_id]
            parent = first_id
            for text in tweets[1:]:
                tid = await self._post_tweet(
                    client, text=text, reply_to=parent,
                )
                if not tid:
                    logger.info(
                        "x thread truncated at %d/%d tweets",
                        len(posted),
                        len(tweets),
                    )
                    break
                posted.append(tid)
                parent = tid

            url = f"https://x.com/i/status/{first_id}"
            return PublishResult(
                ok=True,
                platform=Platform.X,
                draft_id=draft.draft_id,
                post_external_id=first_id,
                post_url=url,
                final_text=tweets[0],
                meta={
                    "thread_count": len(posted),
                    "all_ids": posted,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return PublishResult(
                ok=False,
                platform=Platform.X,
                draft_id=draft.draft_id,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def delete(self, post_external_id: str) -> bool:
        client = self._client or _get_module_client(self.timeout)
        try:
            resp = await client.delete(
                f"{self.api_base}/tweets/{post_external_id}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            return resp.status_code in (200, 204)
        except Exception as exc:  # noqa: BLE001
            logger.info("x delete failed: %s", exc)
            return False

    # ── Internal ─────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }

    async def _post_tweet(
        self,
        client: httpx.AsyncClient,
        *,
        text: str,
        reply_to: str | None,
    ) -> str | None:
        payload: dict[str, Any] = {"text": text}
        if reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to}
        resp = await client.post(
            f"{self.api_base}/tweets",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code not in (200, 201):
            logger.warning(
                "X API returned %s: %s",
                resp.status_code,
                resp.text[:300],
            )
            return None
        try:
            body = resp.json()
        except ValueError:
            return None
        data = body.get("data") or {}
        tid = data.get("id")
        return str(tid) if tid else None


# ── helpers ──────────────────────────────────────────────────────────


def _build_thread(draft: DraftPayload) -> list[str]:
    """Convert main_caption + slides into ordered thread of tweet texts.

    Each tweet is capped at 280 chars (ellipsis on overflow).
    """
    tweets: list[str] = []
    tweets.append(_truncate(draft.main_caption or draft.topic))
    for slide in draft.slides:
        text = slide.final_text or slide.caption or ""
        if not text.strip():
            continue
        tweets.append(_truncate(text))
    if draft.link_url:
        link = draft.link_url.strip()
        if len(link) <= MAX_TWEET_CHARS:
            tweets.append(link)
    return tweets


def _truncate(text: str, limit: int = MAX_TWEET_CHARS) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1].rstrip() + "…"
