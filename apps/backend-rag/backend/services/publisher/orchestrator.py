"""PublisherOrchestrator — fan out a draft to N publishers in parallel.

Design §9.7 Graceful degradation:
- each publisher isolated
- per-publisher retries with exponential backoff
- each success → war_room_posts row (via WarRoomRepository)
- idempotency: if a war_room_post already exists for (draft_id, platform),
  skip re-publish unless ``force=True``

Triggered by:
    EventBus channel war_room_event → event_type=draft_approved
Subscriber: backend/services/publisher/subscriber.py (Sprint 9, separate).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.services.publisher.base import (
    DraftPayload,
    Publisher,
    PublishResult,
)
from backend.services.war_room.models import (
    RegisterTone,
    WarRoomPostCreate,
)
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


@dataclass
class PublisherOrchestratorResult:
    draft_id: Any
    per_platform: list[PublishResult] = field(default_factory=list)
    retries_by_platform: dict[str, int] = field(default_factory=dict)
    skipped_already_published: list[str] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.per_platform if r.ok)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.per_platform if not r.ok)


class PublisherOrchestrator:
    """Fan out to N publishers concurrently with per-platform retry.

    All publishers run in parallel (``asyncio.gather``); retries happen
    *inside* each per-platform task with backoff 0.5s, 2s, 5s.
    """

    DEFAULT_BACKOFFS_S: tuple[float, ...] = (0.5, 2.0, 5.0)

    def __init__(
        self,
        publishers: list[Publisher],
        repo: WarRoomRepository | None = None,
        *,
        max_retries: int = 3,
        backoffs_s: tuple[float, ...] | None = None,
    ) -> None:
        if not publishers:
            raise ValueError("PublisherOrchestrator requires >= 1 publisher")
        self.publishers = publishers
        self.repo = repo
        self.max_retries = max_retries
        self.backoffs_s = backoffs_s or self.DEFAULT_BACKOFFS_S
        self.logger = logger

    async def publish_all(
        self,
        draft: DraftPayload,
        *,
        tone_register: RegisterTone | None = None,
        force: bool = False,
    ) -> PublisherOrchestratorResult:
        result = PublisherOrchestratorResult(draft_id=draft.draft_id)

        # Idempotency check — skip platforms where we already published
        already: dict[str, str] = {}
        if self.repo is not None and not force:
            existing = await self.repo.get_posts_for_draft(draft.draft_id)
            already = {
                p.platform.value: (p.post_external_id or "")
                for p in existing
                if p.post_external_id
            }

        async def _run(publisher: Publisher) -> PublishResult:
            platform_key = publisher.platform_name.value
            if platform_key in already:
                result.skipped_already_published.append(platform_key)
                return PublishResult(
                    ok=True,
                    platform=publisher.platform_name,
                    draft_id=draft.draft_id,
                    post_external_id=already[platform_key],
                    attempts=0,
                    meta={"idempotent_skip": True},
                )
            return await self._publish_with_retry(publisher, draft)

        per_platform = await asyncio.gather(
            *[_run(p) for p in self.publishers],
            return_exceptions=False,
        )
        result.per_platform = list(per_platform)

        # record successes (skip idempotent re-entries; their row already exists)
        if self.repo is not None:
            await self._record_successes(result, tone_register)

        return result

    async def _publish_with_retry(
        self,
        publisher: Publisher,
        draft: DraftPayload,
    ) -> PublishResult:
        platform_key = publisher.platform_name.value
        last_error: str | None = None
        total_attempts = 0

        for attempt in range(1, self.max_retries + 1):
            total_attempts = attempt
            try:
                result = await publisher.publish(draft)
            except Exception as exc:  # noqa: BLE001
                self.logger.info(
                    "publisher %s raised on attempt %d: %s",
                    platform_key,
                    attempt,
                    exc,
                )
                result = PublishResult(
                    ok=False,
                    platform=publisher.platform_name,
                    draft_id=draft.draft_id,
                    attempts=attempt,
                    error=f"{type(exc).__name__}: {exc}",
                )

            result.attempts = attempt

            if result.ok:
                return result

            last_error = result.error
            if attempt < self.max_retries:
                delay = self.backoffs_s[
                    min(attempt - 1, len(self.backoffs_s) - 1)
                ]
                await asyncio.sleep(delay)

        return PublishResult(
            ok=False,
            platform=publisher.platform_name,
            draft_id=draft.draft_id,
            attempts=total_attempts,
            error=last_error or "unknown error",
        )

    async def _record_successes(
        self,
        result: PublisherOrchestratorResult,
        tone_register: RegisterTone | None,
    ) -> None:
        assert self.repo is not None
        for pr in result.per_platform:
            if not pr.ok or pr.meta.get("idempotent_skip"):
                continue
            try:
                await self.repo.create_post(
                    WarRoomPostCreate(
                        draft_id=pr.draft_id,
                        platform=pr.platform,
                        post_external_id=pr.post_external_id,
                        post_url=pr.post_url,
                        tone_register=tone_register,
                        final_text=pr.final_text,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                # recording failure must NOT roll back the publication
                self.logger.warning(
                    "failed to record war_room_post for %s: %s",
                    pr.platform.value,
                    exc,
                )
