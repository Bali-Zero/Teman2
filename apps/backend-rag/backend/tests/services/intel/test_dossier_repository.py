"""Unit tests for IntelRepository with mock asyncpg pool."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.services.intel.dossier_models import (
    ConsumerType,
    DossierCitation,
    DossierFact,
    RefreshReason,
    ResearchDossierCreate,
    TopicCategory,
    TrendSignalCreate,
    TrendSource,
)
from backend.services.intel.dossier_repository import IntelRepository


@pytest.fixture
def repo_and_conn(mock_db_pool):
    pool, conn = mock_db_pool
    repo = IntelRepository(db_pool=pool)
    return repo, conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _trend_row(**overrides):
    row = {
        "id": uuid4(),
        "source": "rss",
        "source_url": "https://example.com",
        "topic": "KBLI 2025 enforcement wave",
        "raw_title": "KBLI 2025 enforcement starts",
        "raw_snippet": "snippet",
        "language": "id",
        "urgency_score": Decimal("72.5"),
        "bali_zero_relevance": Decimal("88.0"),
        "decay_half_life_hours": 48,
        "entities_linked": None,
        "detected_at": _now(),
        "expires_at": _now() + timedelta(hours=48),
        "consumed_by_dossier": None,
    }
    row.update(overrides)
    return row


def _dossier_row(**overrides):
    row = {
        "id": uuid4(),
        "slug": "test-dossier",
        "title": "Test dossier",
        "topic_category": "visa",
        "domains": json.dumps(["chatbot", "warroom"]),
        "public_safe": True,
        "facts": json.dumps([]),
        "numbers": json.dumps([]),
        "citations": json.dumps([]),
        "entities_linked": json.dumps([]),
        "precedents": json.dumps([]),
        "confidence_0_1": Decimal("0.750"),
        "freshness_expiry": _now() + timedelta(days=30),
        "source_signals": None,
        "language": "id",
        "summary_short": "short",
        "summary_medium": "medium",
        "created_at": _now(),
        "updated_at": _now(),
        "archived_at": None,
    }
    row.update(overrides)
    return row


# ── Trend signals ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_append_trend(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=_trend_row())
    sig = await repo.append_trend(TrendSignalCreate(
        source=TrendSource.RSS,
        topic="KBLI 2025 enforcement wave",
        urgency_score=72.5,
        bali_zero_relevance=88.0,
    ))
    assert sig.source == TrendSource.RSS
    assert sig.urgency_score == 72.5
    assert sig.bali_zero_relevance == 88.0


@pytest.mark.asyncio
async def test_recent_trends(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetch = AsyncMock(return_value=[_trend_row(), _trend_row()])
    sigs = await repo.recent_trends(hours=12)
    assert len(sigs) == 2
    conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_top_unconsumed_trends_uses_score_order(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetch = AsyncMock(return_value=[])
    await repo.top_unconsumed_trends(limit=20)
    call_query = conn.fetch.call_args[0][0]
    assert "consumed_by_dossier IS NULL" in call_query
    assert "ORDER BY score DESC" in call_query


@pytest.mark.asyncio
async def test_mark_trend_consumed(repo_and_conn):
    repo, conn = repo_and_conn
    conn.execute = AsyncMock(return_value="UPDATE 1")
    signal_id = uuid4()
    dossier_id = uuid4()
    await repo.mark_trend_consumed(signal_id, dossier_id)
    conn.execute.assert_called_once()


# ── Dossiers ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_dossier_new(repo_and_conn):
    repo, conn = repo_and_conn
    # Transaction helper: pool.acquire() + conn.transaction()
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=None)
    tx_ctx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx_ctx)

    new_row = _dossier_row()
    new_row["was_update"] = False
    conn.fetchrow = AsyncMock(return_value=new_row)
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    d = await repo.upsert_dossier(ResearchDossierCreate(
        slug="b211a-fourth-extension-2026",
        title="B211A",
        topic_category=TopicCategory.VISA,
        freshness_expiry=_now() + timedelta(days=30),
        facts=[DossierFact(claim="A", confidence=0.8)],
        citations=[DossierCitation(norma="Permenkumham 22/2023")],
        public_safe=True,
    ))
    assert d.slug == "test-dossier"  # mock row value
    # no refresh log entry because was_update=False
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_dossier_conflict_logs_refresh(repo_and_conn):
    repo, conn = repo_and_conn
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=None)
    tx_ctx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx_ctx)

    updated_row = _dossier_row()
    updated_row["was_update"] = True
    conn.fetchrow = AsyncMock(return_value=updated_row)
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    await repo.upsert_dossier(ResearchDossierCreate(
        slug="already-exists",
        title="Refresh",
        topic_category=TopicCategory.TAX,
        freshness_expiry=_now() + timedelta(days=30),
        confidence_0_1=0.8,
    ))
    # refresh log written exactly once on conflict
    assert conn.execute.call_count == 1
    executed_query = conn.execute.call_args[0][0]
    assert "dossier_refresh_log" in executed_query


@pytest.mark.asyncio
async def test_get_dossier_by_slug(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=_dossier_row(slug="my-slug"))
    d = await repo.get_dossier_by_slug("my-slug")
    assert d is not None
    assert d.slug == "my-slug"


@pytest.mark.asyncio
async def test_dossiers_for_category_filters_fresh(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetch = AsyncMock(return_value=[_dossier_row(topic_category="visa")])
    res = await repo.dossiers_for_category(TopicCategory.VISA, only_fresh=True)
    assert len(res) == 1
    query = conn.fetch.call_args[0][0]
    assert "freshness_expiry > NOW()" in query


@pytest.mark.asyncio
async def test_expired_dossiers(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetch = AsyncMock(return_value=[])
    await repo.expired_dossiers(limit=50)
    query = conn.fetch.call_args[0][0]
    assert "freshness_expiry < NOW()" in query


@pytest.mark.asyncio
async def test_archive_dossier(repo_and_conn):
    repo, conn = repo_and_conn
    conn.execute = AsyncMock(return_value="UPDATE 1")
    await repo.archive_dossier(uuid4())
    conn.execute.assert_called_once()


# ── Reuse tracking ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_reuse(repo_and_conn):
    repo, conn = repo_and_conn
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    await repo.record_reuse(
        uuid4(),
        ConsumerType.CHATBOT,
        consumer_entity_id="user_123",
        context={"query": "B211A extension rules"},
    )
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_reuse_ratio_with_compiled_and_reads(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value={"ratio": 5.25})
    ratio = await repo.reuse_ratio(days=30)
    assert ratio == 5.25


@pytest.mark.asyncio
async def test_reuse_ratio_zero_when_no_dossiers(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value={"ratio": 0.0})
    ratio = await repo.reuse_ratio(days=30)
    assert ratio == 0.0


@pytest.mark.asyncio
async def test_consumer_coverage(repo_and_conn):
    repo, conn = repo_and_conn
    conn.fetch = AsyncMock(return_value=[
        {"consumer_type": "chatbot", "n": 45},
        {"consumer_type": "warroom", "n": 12},
        {"consumer_type": "crm", "n": 8},
    ])
    cov = await repo.consumer_coverage(days=30)
    assert cov == {"chatbot": 45, "warroom": 12, "crm": 8}


@pytest.mark.asyncio
async def test_log_refresh(repo_and_conn):
    repo, conn = repo_and_conn
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    await repo.log_refresh(
        uuid4(),
        RefreshReason.EXPIRY,
        diff_summary="expired, regenerated",
        old_confidence=0.6,
        new_confidence=0.85,
    )
    conn.execute.assert_called_once()
