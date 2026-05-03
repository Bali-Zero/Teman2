"""Unit tests for WarRoomRepository (mock asyncpg)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

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
    WarRoomDraftCreate,
    WarRoomPostCreate,
)
from backend.services.war_room.repository import WarRoomRepository


@pytest.fixture
def repo_and_conn(mock_db_pool):
    pool, conn = mock_db_pool
    repo = WarRoomRepository(db_pool=pool)
    return repo, conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _draft_row(status: str = "briefed") -> dict:
    now = _now()
    return {
        "id": uuid4(),
        "topic": "test topic",
        "register": None,
        "status": status,
        "brief_json": None,
        "research_json": None,
        "council_debate_json": None,
        "slides_json": None,
        "drafts_json": None,
        "rejection_reason": None,
        "created_at": now,
        "updated_at": now,
        "approved_by": None,
        "approved_at": None,
    }


@pytest.mark.asyncio
async def test_create_draft(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=_draft_row())
    draft = await repo.create_draft(WarRoomDraftCreate(topic="test topic"))
    assert draft.topic == "test topic"
    assert draft.status == DraftStatus.BRIEFED
    conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_update_status_to_approved_sets_approved_at(repo_and_conn):
    repo, conn = repo_and_conn
    row = _draft_row(status="approved")
    row["approved_by"] = "zero"
    row["approved_at"] = _now()
    conn.fetchrow = AsyncMock(return_value=row)
    draft = await repo.update_status(
        uuid4(),
        DraftStatus.APPROVED,
        approved_by="zero",
    )
    assert draft is not None
    assert draft.status == DraftStatus.APPROVED
    assert draft.approved_by == "zero"


@pytest.mark.asyncio
async def test_patch_json_research_only(repo_and_conn):
    repo, conn = repo_and_conn
    row = _draft_row()
    row["research_json"] = {"facts": [1, 2, 3]}
    conn.fetchrow = AsyncMock(return_value=row)
    draft = await repo.patch_json(uuid4(), research_json={"facts": [1, 2, 3]})
    assert draft is not None
    assert draft.research_json == {"facts": [1, 2, 3]}


@pytest.mark.asyncio
async def test_count_registers_last_14d_empty(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetch = AsyncMock(return_value=[])
    counts = await repo.count_registers_last_14d()
    assert counts == {}


@pytest.mark.asyncio
async def test_count_registers_last_14d_with_data(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetch = AsyncMock(return_value=[
        {"register": "analitico", "n": 4},
        {"register": "pedagogico", "n": 2},
        {"register": "ironico", "n": 1},
    ])
    counts = await repo.count_registers_last_14d()
    assert counts == {"analitico": 4, "pedagogico": 2, "ironico": 1}


@pytest.mark.asyncio
async def test_create_post(repo_and_conn):
    repo, conn = repo_and_conn
    now = _now()
    draft_id = uuid4()
    conn.fetchrow = AsyncMock(return_value={
        "id": uuid4(),
        "draft_id": draft_id,
        "platform": "instagram",
        "post_external_id": "ig_17890",
        "post_url": "https://instagram.com/p/abc",
        "register": "analitico",
        "published_at": now,
        "final_text": "caption text",
    })
    post = await repo.create_post(WarRoomPostCreate(
        draft_id=draft_id,
        platform=Platform.INSTAGRAM,
        post_external_id="ig_17890",
        post_url="https://instagram.com/p/abc",
        tone_register=RegisterTone.ANALITICO,
        final_text="caption text",
    ))
    assert post.draft_id == draft_id
    assert post.platform == Platform.INSTAGRAM


@pytest.mark.asyncio
async def test_record_metric(repo_and_conn):
    repo, conn = repo_and_conn
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    await repo.record_metric(
        uuid4(),
        "reach",
        15000.0,
        MetricSource.META_GRAPH,
    )
    conn.execute.assert_called_once()
    # second positional arg should contain the metric name
    assert "reach" in conn.execute.call_args[0]


@pytest.mark.asyncio
async def test_attribute_lead_with_revenue(repo_and_conn):
    repo, conn = repo_and_conn
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    await repo.attribute_lead(
        uuid4(),
        utm_campaign="warroom_b211a",
        utm_source="instagram",
        conversion_stage=ConversionStage.CLIENT,
        revenue_idr=Decimal("25000000"),
    )
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_record_rejection(repo_and_conn):
    repo, conn = repo_and_conn
    now = _now()
    draft_id = uuid4()
    conn.fetchrow = AsyncMock(return_value={
        "id": uuid4(),
        "draft_id": draft_id,
        "reason": "clickbait",
        "reason_detail": "trap metaphor",
        "rejected_by": "validator",
        "rejected_at": now,
    })
    rej = await repo.record_rejection(
        draft_id,
        RejectionReason.CLICKBAIT,
        RejectedBy.VALIDATOR,
        reason_detail="trap metaphor",
    )
    assert rej.reason == RejectionReason.CLICKBAIT
    assert rej.rejected_by == RejectedBy.VALIDATOR


@pytest.mark.asyncio
async def test_record_missed_run(repo_and_conn):
    repo, conn = repo_and_conn
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    await repo.record_missed_run(
        _now(),
        MissedRunReason.PRO_OFFLINE,
        details={"last_heartbeat": "2026-04-18T09:00:00Z"},
    )
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_record_cost_and_total(repo_and_conn):
    repo, conn = repo_and_conn
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    draft_id = uuid4()
    await repo.record_cost(
        draft_id,
        CostType.IMAGEN_ULTRA,
        Decimal("0.060000"),
        meta={"model": "imagen-4.0-ultra"},
    )
    conn.execute.assert_called_once()

    conn.fetchrow = AsyncMock(return_value={"total": Decimal("0.160000")})
    total = await repo.total_cost_for_draft(draft_id)
    assert total == Decimal("0.160000")
