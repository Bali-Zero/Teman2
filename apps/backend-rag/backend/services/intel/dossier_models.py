"""Pydantic models for Intel Scraper dossier system (migration 113).

Reference: docs/war-room-2.0-design.md §15.4, §21.

Two primary artifacts:
- TrendSignal: raw normalized signal (TTL 48-72h)
- ResearchDossier: structured compiled dossier (TTL 30d, 10 consumers)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrendSource(str, Enum):
    XAI = "xai"
    GTRENDS = "gtrends"
    REDDIT = "reddit"
    RSS = "rss"
    SCRAPER = "scraper"
    MANUAL = "manual"


class TopicCategory(str, Enum):
    VISA = "visa"
    TAX = "tax"
    KBLI = "kbli"
    PROPERTY = "property"
    COMPLIANCE = "compliance"
    CULTURAL = "cultural"
    MACRO = "macro"
    FINANCE = "finance"
    CRYPTO = "crypto"
    OTHER = "other"


class ConsumerType(str, Enum):
    """10 dossier consumers + 4 cognitive layer consumers (§16)."""

    CHATBOT = "chatbot"
    CRM = "crm"
    NLM = "nlm"
    CURIOSITY = "curiosity"
    COUNCIL = "council"
    WARROOM = "warroom"
    NEWSLETTER = "newsletter"
    GUARDIAN = "guardian"
    TEAM = "team"
    PUBLIC = "public"
    # Cognitive layers (§17)
    CONNECTOR = "connector"
    ANOMALY = "anomaly"
    STRATEGOS = "strategos"
    ORACLE = "oracle"


class RefreshReason(str, Enum):
    EXPIRY = "expiry"
    NEW_SOURCE = "new_source"
    MANUAL = "manual"
    CONSUMER_REQUEST = "consumer_request"
    ANOMALY_TRIGGER = "anomaly_trigger"


# ── TrendSignal ─────────────────────────────────────────────────────────


class TrendSignal(BaseModel):
    """Raw normalized signal from Intel sources. TTL 48-72h."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: TrendSource
    source_url: str | None = None
    topic: str
    raw_title: str | None = None
    raw_snippet: str | None = None
    language: str | None = None
    urgency_score: float = Field(ge=0, le=100)
    bali_zero_relevance: float | None = Field(default=None, ge=0, le=100)
    decay_half_life_hours: int = 48
    entities_linked: list[dict[str, Any]] | None = None
    detected_at: datetime
    expires_at: datetime | None = None
    consumed_by_dossier: UUID | None = None


class TrendSignalCreate(BaseModel):
    source: TrendSource
    topic: str
    urgency_score: float = Field(ge=0, le=100)
    source_url: str | None = None
    raw_title: str | None = None
    raw_snippet: str | None = None
    language: str | None = None
    bali_zero_relevance: float | None = Field(default=None, ge=0, le=100)
    decay_half_life_hours: int = 48
    entities_linked: list[dict[str, Any]] | None = None


# ── ResearchDossier building blocks ────────────────────────────────────


class DossierFact(BaseModel):
    """A single verified claim with provenance."""

    claim: str
    source_url: str | None = None
    confidence: float = Field(ge=0, le=1)
    verified_at: datetime | None = None


class DossierNumber(BaseModel):
    """A numeric datum (statistic, threshold, fee amount)."""

    metric: str
    value: float
    unit: str | None = None
    period: str | None = None
    source: str | None = None


class DossierCitation(BaseModel):
    """Legal norm citation — required by zantara_core.py citation rules."""

    norma: str
    articolo: str | None = None
    comma: str | None = None
    quote_exact: str | None = None
    year: int | None = None


class DossierEntity(BaseModel):
    """KG entity reference."""

    kg_entity_id: str
    type: str
    role: str | None = None


class DossierPrecedent(BaseModel):
    """Reference to a prior dossier on related topic."""

    dossier_id_related: UUID
    relation: str


# ── ResearchDossier ────────────────────────────────────────────────────


class ResearchDossier(BaseModel):
    """Structured dossier — 30d TTL, consumed by 10+ consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    topic_category: TopicCategory
    domains: list[str] = Field(default_factory=list)
    public_safe: bool = False

    facts: list[DossierFact] = Field(default_factory=list)
    numbers: list[DossierNumber] = Field(default_factory=list)
    citations: list[DossierCitation] = Field(default_factory=list)
    entities_linked: list[DossierEntity] = Field(default_factory=list)
    precedents: list[DossierPrecedent] = Field(default_factory=list)

    confidence_0_1: float = Field(ge=0, le=1, default=0.5)
    freshness_expiry: datetime

    source_signals: list[UUID] | None = None
    language: str = "id"
    summary_short: str | None = Field(default=None, max_length=140)
    summary_medium: str | None = Field(default=None, max_length=500)

    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class ResearchDossierCreate(BaseModel):
    slug: str
    title: str
    topic_category: TopicCategory
    freshness_expiry: datetime
    domains: list[str] = Field(default_factory=list)
    public_safe: bool = False
    facts: list[DossierFact] = Field(default_factory=list)
    numbers: list[DossierNumber] = Field(default_factory=list)
    citations: list[DossierCitation] = Field(default_factory=list)
    entities_linked: list[DossierEntity] = Field(default_factory=list)
    precedents: list[DossierPrecedent] = Field(default_factory=list)
    confidence_0_1: float = Field(ge=0, le=1, default=0.5)
    source_signals: list[UUID] | None = None
    language: str = "id"
    summary_short: str | None = Field(default=None, max_length=140)
    summary_medium: str | None = Field(default=None, max_length=500)


# ── Event payloads ─────────────────────────────────────────────────────


class IntelEventPayload(BaseModel):
    """pg_notify('intel_event', ...) shape — always <= 8 KB."""

    event_type: str
    occurred_at: datetime
    signal_id: UUID | None = None
    dossier_id: UUID | None = None
    source: str | None = None
    topic: str | None = None
    slug: str | None = None
    topic_category: str | None = None
    urgency_score: float | None = None
    public_safe: bool | None = None
