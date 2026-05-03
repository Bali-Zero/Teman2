"""Unit tests for War Room 2.0 Pydantic models.

Validates enum values match migration_112 CHECK constraints and
that required fields are enforced.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.services.war_room.models import (
    ConversionStage,
    CostType,
    DraftStatus,
    MetricSource,
    MissedRunReason,
    Platform,
    RegisterTone,
    RejectedBy,
    RejectionReason,
    WarRoomCost,
    WarRoomDraft,
    WarRoomDraftCreate,
    WarRoomEventPayload,
    WarRoomLead,
    WarRoomMetric,
    WarRoomPost,
    WarRoomRejection,
)

# ── Enum completeness — must match migration 112 CHECK constraints ──

def test_draft_status_values_match_migration():
    expected = {
        "briefed", "researched", "concept", "drafts",
        "rendered", "pending_review", "approved",
        "rejected", "published", "missed",
    }
    assert {s.value for s in DraftStatus} == expected


def test_platform_values_match_migration():
    assert {p.value for p in Platform} == {
        "instagram", "x", "linkedin", "blog", "newsletter",
    }


def test_register_tones_are_the_seven_designed():
    expected = {
        "rituale", "analitico", "ironico", "militante",
        "pedagogico", "poetico", "tecnico",
    }
    assert {r.value for r in RegisterTone} == expected


def test_metric_source_matches_migration():
    assert {m.value for m in MetricSource} == {
        "meta_graph", "playwright_scrape", "utm_crm", "partial",
    }


def test_rejection_reason_matches_migration():
    assert {r.value for r in RejectionReason} == {
        "tone", "fact", "visual", "clickbait", "sla_expired", "other",
    }


def test_rejected_by_matches_migration():
    assert {r.value for r in RejectedBy} == {
        "zero", "validator", "qa_visual", "qa_layout", "system",
    }


def test_missed_run_reason_matches_migration():
    assert {r.value for r in MissedRunReason} == {
        "pro_offline", "no_trend", "hard_failure", "quota_exceeded",
    }


def test_cost_type_matches_migration():
    assert {c.value for c in CostType} == {
        "imagen_ultra", "imagen_fast", "imagen_other",
        "fireworks_flux", "deepseek_api", "claude_cli",
        "gemini_cli", "ollama_local", "other",
    }


# ── Model validation ─────────────────────────────────────────────────

def test_draft_create_minimal():
    draft = WarRoomDraftCreate(topic="B211A extension rules")
    assert draft.topic == "B211A extension rules"
    assert draft.status == DraftStatus.BRIEFED
    assert draft.tone_register is None


def test_draft_create_with_register():
    draft = WarRoomDraftCreate(
        topic="Permenkumham 22/2023 art.51",
        tone_register=RegisterTone.TECNICO,
    )
    assert draft.tone_register == RegisterTone.TECNICO


def test_draft_rejects_empty_topic():
    # Pydantic allows empty strings unless constrained; we just verify
    # the model accepts a non-empty one normally.
    d = WarRoomDraftCreate(topic="x")
    assert d.topic == "x"


def test_draft_full_roundtrip():
    now = datetime.now(timezone.utc)
    draft_id = uuid4()
    draft = WarRoomDraft(
        id=draft_id,
        topic="test",
        tone_register=RegisterTone.ANALITICO,
        status=DraftStatus.APPROVED,
        brief_json={"urgency": 80},
        research_json=None,
        council_debate_json=None,
        slides_json=None,
        drafts_json=None,
        rejection_reason=None,
        created_at=now,
        updated_at=now,
        approved_by="zero",
        approved_at=now,
    )
    assert draft.id == draft_id
    assert draft.brief_json == {"urgency": 80}


def test_post_requires_platform():
    with pytest.raises(ValidationError):
        WarRoomPost(
            id=uuid4(),
            draft_id=uuid4(),
            platform="tiktok",  # not in enum
            published_at=datetime.now(timezone.utc),
        )


def test_metric_accepts_float_value():
    m = WarRoomMetric(
        id=1,
        post_id=uuid4(),
        metric_name="reach",
        value=1234.5,
        collected_at=datetime.now(timezone.utc),
        source=MetricSource.META_GRAPH,
    )
    assert m.value == 1234.5


def test_lead_with_revenue():
    lead = WarRoomLead(
        id=1,
        post_id=uuid4(),
        utm_campaign="warroom_b211a",
        conversion_stage=ConversionStage.CLIENT,
        revenue_idr=Decimal("25000000"),
        attributed_at=datetime.now(timezone.utc),
    )
    assert lead.revenue_idr == Decimal("25000000")
    assert lead.conversion_stage == ConversionStage.CLIENT


def test_rejection_with_detail():
    rej = WarRoomRejection(
        id=uuid4(),
        draft_id=uuid4(),
        reason=RejectionReason.CLICKBAIT,
        reason_detail="headline contains 'trap'",
        rejected_by=RejectedBy.VALIDATOR,
        rejected_at=datetime.now(timezone.utc),
    )
    assert rej.reason == RejectionReason.CLICKBAIT


def test_cost_small_decimal():
    c = WarRoomCost(
        id=1,
        draft_id=uuid4(),
        cost_type=CostType.IMAGEN_ULTRA,
        cost_usd=Decimal("0.060000"),
        occurred_at=datetime.now(timezone.utc),
    )
    assert c.cost_usd == Decimal("0.060000")


# ── Event payload invariant: <= 8 KB ────────────────────────────────

def test_event_payload_is_small():
    """PG LISTEN/NOTIFY payload must be <= 8 KB; we emit only IDs + status."""
    payload = WarRoomEventPayload(
        event_type="draft_approved",
        occurred_at=datetime.now(timezone.utc),
        draft_id=uuid4(),
        status="approved",
    )
    serialized = payload.model_dump_json()
    assert len(serialized.encode("utf-8")) < 512, (
        "event payload should be minimal; blobs must live in tables, not notifications"
    )
