"""Tests for the 5 priority consumers (mock injected fn)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.dossier_fanout.consumers import (
    CRMAlertingConsumer,
    CuriosityConsumer,
    NLMFeederConsumer,
    WarRoomDirectorConsumer,
    ZantaraRAGConsumer,
    _result_from_fn_output,
)
from backend.services.intel.dossier_models import ConsumerType, ResearchDossier, TopicCategory


def _dossier() -> ResearchDossier:
    now = datetime.now(timezone.utc)
    return ResearchDossier(
        id=uuid4(),
        slug="test-abc",
        title="T",
        topic_category=TopicCategory.VISA,
        domains=["chatbot", "crm", "nlm", "curiosity", "warroom"],
        public_safe=True,
        facts=[],
        numbers=[],
        citations=[],
        entities_linked=[],
        precedents=[],
        confidence_0_1=0.7,
        freshness_expiry=now + timedelta(days=30),
        source_signals=None,
        language="it",
        summary_short="s",
        summary_medium="m",
        created_at=now,
        updated_at=now,
        archived_at=None,
    )


# ── _result_from_fn_output ──────────────────────────────────


def test_result_from_fn_output_non_dict_fails():
    r = _result_from_fn_output(ConsumerType.CHATBOT, None)
    assert r.ok is False
    assert "non-dict" in (r.error or "")


def test_result_from_fn_output_not_ok_passes_through_error():
    r = _result_from_fn_output(
        ConsumerType.CRM,
        {"ok": False, "error": "crm down", "detail": "500"},
    )
    assert r.ok is False
    assert r.error == "crm down"
    assert r.meta["detail"] == "500"


def test_result_from_fn_output_ok_preserves_entity_id_and_meta():
    r = _result_from_fn_output(
        ConsumerType.CHATBOT,
        {"ok": True, "entity_id": "qdrant:42", "dimensions": 1536},
    )
    assert r.ok is True
    assert r.entity_id == "qdrant:42"
    assert r.meta == {"dimensions": 1536}


# ── Per-consumer ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zantara_rag_consumer_delegates():
    fn = AsyncMock(return_value={"ok": True, "entity_id": "qdrant:77"})
    c = ZantaraRAGConsumer(rag_upsert_fn=fn)
    assert c.consumer_type == ConsumerType.CHATBOT
    r = await c.consume(_dossier())
    assert r.ok is True
    assert r.entity_id == "qdrant:77"
    fn.assert_awaited_once()


@pytest.mark.asyncio
async def test_crm_alerting_consumer_error_path():
    fn = AsyncMock(return_value={"ok": False, "error": "no contacts"})
    c = CRMAlertingConsumer(crm_alert_fn=fn)
    r = await c.consume(_dossier())
    assert r.ok is False
    assert "no contacts" in (r.error or "")


@pytest.mark.asyncio
async def test_nlm_feeder_consumer_requires_public_safe():
    fn = AsyncMock(return_value={"ok": True, "entity_id": "nlm:nb-2:src-1"})
    c = NLMFeederConsumer(nlm_upload_fn=fn)
    assert c.require_public_safe is True
    r = await c.consume(_dossier())
    assert r.ok is True
    assert r.entity_id == "nlm:nb-2:src-1"


@pytest.mark.asyncio
async def test_curiosity_consumer_meta_preserved():
    fn = AsyncMock(return_value={
        "ok": True,
        "entity_id": "gap:visa-b211a-2026",
        "gaps_closed": 2,
    })
    c = CuriosityConsumer(curiosity_close_fn=fn)
    r = await c.consume(_dossier())
    assert r.ok is True
    assert r.meta.get("gaps_closed") == 2


@pytest.mark.asyncio
async def test_warroom_director_consumer_delegates():
    fn = AsyncMock(return_value={"ok": True, "entity_id": "war_room.draft_hint"})
    c = WarRoomDirectorConsumer(warroom_notify_fn=fn)
    assert c.consumer_type == ConsumerType.WARROOM
    r = await c.consume(_dossier())
    assert r.ok is True


@pytest.mark.asyncio
async def test_consumer_fn_none_return_treated_as_failure():
    fn = AsyncMock(return_value=None)
    c = ZantaraRAGConsumer(rag_upsert_fn=fn)
    r = await c.consume(_dossier())
    assert r.ok is False
    assert "non-dict" in (r.error or "")
