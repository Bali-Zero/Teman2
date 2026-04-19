"""Unit tests for Intel dossier Pydantic models (migration 113)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.services.intel.dossier_models import (
    ConsumerType,
    DossierCitation,
    DossierEntity,
    DossierFact,
    DossierNumber,
    IntelEventPayload,
    RefreshReason,
    ResearchDossierCreate,
    TopicCategory,
    TrendSignalCreate,
    TrendSource,
)

# ── Enums match migration 113 CHECK constraints ──

def test_trend_source_values_match_migration():
    assert {s.value for s in TrendSource} == {
        "xai", "gtrends", "reddit", "rss", "scraper", "manual",
    }


def test_topic_category_values_match_migration():
    assert {c.value for c in TopicCategory} == {
        "visa", "tax", "kbli", "property", "compliance",
        "cultural", "macro", "finance", "crypto", "other",
    }


def test_consumer_type_includes_10_dossier_consumers_plus_4_cognitive():
    """Design §16 defines 10 consumers; §17 adds 4 cognitive layers."""
    base_consumers = {
        "chatbot", "crm", "nlm", "curiosity", "council",
        "warroom", "newsletter", "guardian", "team", "public",
    }
    cognitive = {"connector", "anomaly", "strategos", "oracle"}
    assert {c.value for c in ConsumerType} == base_consumers | cognitive


def test_refresh_reason_values_match_migration():
    assert {r.value for r in RefreshReason} == {
        "expiry", "new_source", "manual", "consumer_request", "anomaly_trigger",
    }


# ── TrendSignalCreate ─────────────────────────────────────────────────

def test_trend_signal_create_minimal():
    sig = TrendSignalCreate(
        source=TrendSource.RSS,
        topic="KBLI 2025 new enforcement wave",
        urgency_score=72.5,
    )
    assert sig.urgency_score == 72.5
    assert sig.decay_half_life_hours == 48


def test_trend_signal_urgency_range_enforced():
    with pytest.raises(ValidationError):
        TrendSignalCreate(
            source=TrendSource.RSS,
            topic="out of range",
            urgency_score=150,
        )
    with pytest.raises(ValidationError):
        TrendSignalCreate(
            source=TrendSource.RSS,
            topic="negative",
            urgency_score=-1,
        )


def test_trend_signal_relevance_range_enforced():
    with pytest.raises(ValidationError):
        TrendSignalCreate(
            source=TrendSource.XAI,
            topic="x",
            urgency_score=50,
            bali_zero_relevance=101,
        )


# ── Dossier building blocks ───────────────────────────────────────────

def test_dossier_fact_confidence_range():
    f = DossierFact(claim="DJP Coretax active since 2025", confidence=0.9)
    assert 0 <= f.confidence <= 1
    with pytest.raises(ValidationError):
        DossierFact(claim="x", confidence=1.5)


def test_dossier_number_with_period():
    n = DossierNumber(
        metric="B211A extensions issued",
        value=847312,
        unit="count",
        period="2025",
        source="Ditjen Imigrasi annual report",
    )
    assert n.value == 847312


def test_dossier_citation_minimal():
    c = DossierCitation(norma="Permenkumham 22/2023")
    assert c.norma == "Permenkumham 22/2023"


def test_dossier_entity_requires_kg_id():
    with pytest.raises(ValidationError):
        DossierEntity(type="Visa")  # missing kg_entity_id
    e = DossierEntity(kg_entity_id="visa:B211A", type="Visa", role="subject")
    assert e.kg_entity_id == "visa:B211A"


# ── ResearchDossierCreate ─────────────────────────────────────────────

def test_dossier_create_minimal():
    expiry = datetime.now(timezone.utc) + timedelta(days=30)
    d = ResearchDossierCreate(
        slug="b211a-fourth-extension-2026",
        title="B211A fourth extension conditions",
        topic_category=TopicCategory.VISA,
        freshness_expiry=expiry,
    )
    assert d.public_safe is False  # default is safer
    assert d.confidence_0_1 == 0.5
    assert d.language == "id"


def test_dossier_create_with_facts_and_citations():
    expiry = datetime.now(timezone.utc) + timedelta(days=30)
    d = ResearchDossierCreate(
        slug="test-dossier",
        title="Test",
        topic_category=TopicCategory.TAX,
        freshness_expiry=expiry,
        facts=[DossierFact(claim="fact A", confidence=0.8)],
        citations=[DossierCitation(norma="PP 55/2022")],
    )
    assert len(d.facts) == 1
    assert len(d.citations) == 1


def test_dossier_summary_length_caps():
    expiry = datetime.now(timezone.utc) + timedelta(days=30)
    with pytest.raises(ValidationError):
        ResearchDossierCreate(
            slug="x",
            title="x",
            topic_category=TopicCategory.OTHER,
            freshness_expiry=expiry,
            summary_short="x" * 200,  # > 140
        )
    with pytest.raises(ValidationError):
        ResearchDossierCreate(
            slug="y",
            title="y",
            topic_category=TopicCategory.OTHER,
            freshness_expiry=expiry,
            summary_medium="x" * 600,  # > 500
        )


def test_dossier_confidence_range():
    expiry = datetime.now(timezone.utc) + timedelta(days=30)
    with pytest.raises(ValidationError):
        ResearchDossierCreate(
            slug="bad",
            title="bad",
            topic_category=TopicCategory.OTHER,
            freshness_expiry=expiry,
            confidence_0_1=1.5,
        )


# ── IntelEventPayload ─────────────────────────────────────────────────

def test_event_payload_size_invariant_under_1kb():
    payload = IntelEventPayload(
        event_type="dossier_created",
        occurred_at=datetime.now(timezone.utc),
        dossier_id=uuid4(),
        slug="test-slug-" + "x" * 50,
        topic_category="visa",
        public_safe=False,
    )
    serialized = payload.model_dump_json()
    assert len(serialized.encode("utf-8")) < 1024


def test_event_payload_for_trend_signal():
    payload = IntelEventPayload(
        event_type="trend_signal_detected",
        occurred_at=datetime.now(timezone.utc),
        signal_id=uuid4(),
        source="rss",
        topic="new",
        urgency_score=85.0,
    )
    dumped = payload.model_dump(exclude_none=True)
    assert dumped["event_type"] == "trend_signal_detected"
    assert dumped["urgency_score"] == 85.0
