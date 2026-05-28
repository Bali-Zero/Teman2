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
    """A single slide / frame within a carousel / thread.

    P1.4 (2026-05-26): add ``alt_text`` for accessibility — IG Graph API
    supports alt-text per carousel item via ``image_alt_text`` parameter.
    See: https://developers.facebook.com/docs/instagram-platform/content-publishing
    Reasoning panel: editorial regulatory carouseli (Bali Zero) MUST have
    per-slide alt-text — UU PDP + accessibility = MANDATORY, not optional.
    """

    slide_number: int
    image_url: str
    caption: str | None = None
    final_text: str | None = None
    alt_text: str | None = None  # P1.4 (2026-05-26): IG accessibility per-slide


@dataclass
class DraftPayload:
    """Everything a publisher needs to know about a draft to publish it.

    Kept intentionally small: publishers should not pull DB-heavy objects.

    P1.4 (2026-05-26) additions per 4-LLM panel:
      - ``first_comment``: auto-posted as first comment after publish.
        Used by Bali Zero editorial carouseli for sources + caveats verbatim
        (NOT hashtag stuffing — that goes inline in ``main_caption`` or
        as the ``hashtags`` field).
      - ``approval_state`` + ``approval_actor`` + ``approval_timestamp``:
        regulatory editorial NEVER auto-publishes. Convergence 4/4 panel.
        Publisher MUST refuse ``publish()`` unless approval_state == "approved".
      - ``scheduled_publish_at``: optional scheduling AFTER approval.
        Auto-dispatch can fire only on (approved AND scheduled_publish_at <= now).
      - ``cover_alt_text``: accessibility for the cover frame itself.
    """

    draft_id: UUID
    topic: str
    tone_register: RegisterTone | None
    cover_image_url: str
    main_caption: str  # IG caption / X first tweet / LI post
    slides: list[SlidePayload] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    link_url: str | None = None  # e.g. balizero.com/kbli/51010 with UTM
    cover_alt_text: str | None = None  # P1.4: cover frame accessibility
    first_comment: str | None = None  # P1.4: auto-posted post-publish
    approval_state: str = "pending"  # P1.4: "pending" | "approved" | "rejected"
    approval_actor: str | None = None  # P1.4: email of approver
    approval_timestamp: str | None = None  # P1.4: ISO8601 of approval
    scheduled_publish_at: str | None = None  # P1.4: ISO8601 of scheduled dispatch


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
    async def validate(self, draft: DraftPayload) -> ValidationResult: ...

    @abstractmethod
    async def publish(self, draft: DraftPayload) -> PublishResult: ...

    @abstractmethod
    async def delete(self, post_external_id: str) -> bool:
        """Best-effort rollback. Return True on success, False on any failure."""
        ...
