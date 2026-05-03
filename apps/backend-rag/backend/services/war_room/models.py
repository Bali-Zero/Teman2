"""Pydantic models for War Room 2.0 tables.

Mirrors the SQL schema in migration_112_war_room_tables.py.
Reference: docs/war-room-2.0-design.md §7.1
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DraftStatus(str, Enum):
    BRIEFED = "briefed"
    RESEARCHED = "researched"
    CONCEPT = "concept"
    DRAFTS = "drafts"
    RENDERED = "rendered"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    MISSED = "missed"


class Platform(str, Enum):
    INSTAGRAM = "instagram"
    X = "x"
    LINKEDIN = "linkedin"
    BLOG = "blog"
    NEWSLETTER = "newsletter"


class RegisterTone(str, Enum):
    RITUALE = "rituale"
    ANALITICO = "analitico"
    IRONICO = "ironico"
    MILITANTE = "militante"
    PEDAGOGICO = "pedagogico"
    POETICO = "poetico"
    TECNICO = "tecnico"


class MetricSource(str, Enum):
    META_GRAPH = "meta_graph"
    PLAYWRIGHT_SCRAPE = "playwright_scrape"
    UTM_CRM = "utm_crm"
    PARTIAL = "partial"


class RejectionReason(str, Enum):
    TONE = "tone"
    FACT = "fact"
    VISUAL = "visual"
    CLICKBAIT = "clickbait"
    SLA_EXPIRED = "sla_expired"
    OTHER = "other"


class RejectedBy(str, Enum):
    ZERO = "zero"
    VALIDATOR = "validator"
    QA_VISUAL = "qa_visual"
    QA_LAYOUT = "qa_layout"
    SYSTEM = "system"


class MissedRunReason(str, Enum):
    PRO_OFFLINE = "pro_offline"
    NO_TREND = "no_trend"
    HARD_FAILURE = "hard_failure"
    QUOTA_EXCEEDED = "quota_exceeded"


class CostType(str, Enum):
    IMAGEN_ULTRA = "imagen_ultra"
    IMAGEN_FAST = "imagen_fast"
    IMAGEN_OTHER = "imagen_other"
    FIREWORKS_FLUX = "fireworks_flux"
    DEEPSEEK_API = "deepseek_api"
    CLAUDE_CLI = "claude_cli"
    GEMINI_CLI = "gemini_cli"
    OLLAMA_LOCAL = "ollama_local"
    OTHER = "other"


class ConversionStage(str, Enum):
    LEAD = "lead"
    QUALIFIED = "qualified"
    CLIENT = "client"


class WarRoomDraft(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    topic: str
    tone_register: RegisterTone | None = None
    status: DraftStatus = DraftStatus.BRIEFED
    brief_json: dict[str, Any] | None = None
    research_json: dict[str, Any] | None = None
    council_debate_json: dict[str, Any] | None = None
    slides_json: dict[str, Any] | None = None
    drafts_json: dict[str, Any] | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None


class WarRoomDraftCreate(BaseModel):
    topic: str
    tone_register: RegisterTone | None = None
    status: DraftStatus = DraftStatus.BRIEFED
    brief_json: dict[str, Any] | None = None


class WarRoomPost(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    draft_id: UUID
    platform: Platform
    post_external_id: str | None = None
    post_url: str | None = None
    tone_register: RegisterTone | None = None
    published_at: datetime
    final_text: str | None = None


class WarRoomPostCreate(BaseModel):
    draft_id: UUID
    platform: Platform
    post_external_id: str | None = None
    post_url: str | None = None
    tone_register: RegisterTone | None = None
    final_text: str | None = None


class WarRoomMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: UUID
    metric_name: str = Field(description="reach|impressions|saves|shares|clicks|leads_attributed|likes|comments")
    value: float
    collected_at: datetime
    source: MetricSource


class WarRoomLead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: UUID
    contact_id: UUID | None = None
    utm_campaign: str | None = None
    utm_medium: str | None = None
    utm_source: str | None = None
    attributed_at: datetime
    conversion_stage: ConversionStage | None = None
    revenue_idr: Decimal | None = None


class WarRoomRejection(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    draft_id: UUID
    reason: RejectionReason
    reason_detail: str | None = None
    rejected_by: RejectedBy
    rejected_at: datetime


class WarRoomMissedRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scheduled_at: datetime
    skipped_reason: MissedRunReason
    details_json: dict[str, Any] | None = None
    notified_zero: bool = False
    created_at: datetime


class WarRoomCost(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    draft_id: UUID | None = None
    cost_type: CostType
    cost_usd: Decimal
    occurred_at: datetime
    meta_json: dict[str, Any] | None = None


class WarRoomEventPayload(BaseModel):
    """Payload shape for pg_notify('war_room_event', ...) emitted by triggers.

    Always small (<= 8 KB) — contains IDs + status + uri, never blobs.
    """

    event_type: str
    occurred_at: datetime
    draft_id: UUID | None = None
    post_id: UUID | None = None
    status: str | None = None
    platform: str | None = None
