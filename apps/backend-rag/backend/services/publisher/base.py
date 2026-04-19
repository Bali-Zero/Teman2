"""Publisher ABC + DraftPayload data contracts."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from backend.services.war_room.models import Platform, RegisterTone

logger = logging.getLogger(__name__)


class PublisherError(RuntimeError):
    """Raised on configuration errors (missing tokens, bad platform setup).

    Per-call publication failures surface in :class:`PublishResult.ok=False`
    — not raised — so orchestrator can fan out across platforms without
    crashing.
    """


@dataclass
class SlidePayload:
    """A single slide / frame within a carousel / thread."""

    slide_number: int
    image_url: str
    caption: str | None = None
    final_text: str | None = None


@dataclass
class DraftPayload:
    """Everything a publisher needs to know about a draft to publish it.

    Kept intentionally small: publishers should not pull DB-heavy objects.
    """

    draft_id: UUID
    topic: str
    tone_register: RegisterTone | None
    cover_image_url: str
    main_caption: str            # IG caption / X first tweet / LI post
    slides: list[SlidePayload] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    link_url: str | None = None  # e.g. balizero.com/kbli/51010 with UTM


@dataclass
class ValidationResult:
    ok: bool
    platform: Platform
    issues: list[str] = field(default_factory=list)


@dataclass
class PublishResult:
    ok: bool
    platform: Platform
    draft_id: UUID
    post_external_id: str | None = None
    post_url: str | None = None
    final_text: str | None = None
    attempts: int = 0
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class Publisher(ABC):
    """Abstract interface for platform publishers."""

    platform_name: Platform

    @abstractmethod
    async def validate(self, draft: DraftPayload) -> ValidationResult:
        ...

    @abstractmethod
    async def publish(self, draft: DraftPayload) -> PublishResult:
        ...

    @abstractmethod
    async def delete(self, post_external_id: str) -> bool:
        """Best-effort rollback. Return True on success, False on any failure."""
        ...
