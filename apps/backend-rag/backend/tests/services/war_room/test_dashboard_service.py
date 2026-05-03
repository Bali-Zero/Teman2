"""Tests for DashboardService aggregate queries (mock asyncpg)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.war_room.dashboard_service import (
    PIE_DOMINANCE_ALERT_PCT,
    DashboardService,
    _normalize_by_type,
)
from backend.services.war_room.repository import WarRoomRepository


@pytest.fixture
def repo_and_service(mock_db_pool):
    pool, conn = mock_db_pool
    repo = WarRoomRepository(db_pool=pool)
    return repo, conn, DashboardService(repo=repo)


# ── _normalize_by_type helper ────────────────────────────────


def test_normalize_by_type_none_returns_empty():
    assert _normalize_by_type(None) == {}


def test_normalize_by_type_dict_converts_values():
    assert _normalize_by_type({"a": Decimal("0.06"), "b": 0.02}) == {
        "a": 0.06,
        "b": 0.02,
    }


def test_normalize_by_type_json_string_parses():
    assert _normalize_by_type('{"imagen_ultra": 0.06}') == {"imagen_ultra": 0.06}


def test_normalize_by_type_invalid_json_returns_empty():
    assert _normalize_by_type("not json") == {}


# ── 1. Timeline ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timeline_defaults_14_days_and_clamps(repo_and_service):
    _, conn, svc = repo_and_service
    conn.fetch = AsyncMock(return_value=[])
    await svc.timeline(days=7)  # invalid, clamps to 14
    assert conn.fetch.call_args.args[1] == 14


@pytest.mark.asyncio
async def test_timeline_returns_buckets(repo_and_service):
    _, conn, svc = repo_and_service
    conn.fetch = AsyncMock(return_value=[
        {
            "day": date(2026, 4, 18),
            "register": "analitico",
            "post_count": 3,
        },
        {
            "day": date(2026, 4, 18),
            "register": "ironico",
            "post_count": 1,
        },
    ])
    buckets = await svc.timeline(days=14)
    assert len(buckets) == 2
    first = buckets[0].to_dict()
    assert first["day"] == "2026-04-18"
    assert first["register"] == "analitico"
    assert first["post_count"] == 3


# ── 2. Heatmap ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_heatmap_cells(repo_and_service):
    _, conn, svc = repo_and_service
    conn.fetch = AsyncMock(return_value=[
        {
            "register": "analitico",
            "metric_name": "reach",
            "avg_value": 1234.5,
            "sample_count": 8,
        },
    ])
    cells = await svc.register_performance_heatmap(days=30)
    assert len(cells) == 1
    d = cells[0].to_dict()
    assert d["avg_value"] == 1234.5
    assert d["sample_count"] == 8


# ── 3. Distribution + alert ──────────────────────────────────


@pytest.mark.asyncio
async def test_distribution_no_alert_under_threshold(repo_and_service):
    _, conn, svc = repo_and_service
    conn.fetch = AsyncMock(return_value=[
        {"register": "analitico", "post_count": 3},
        {"register": "tecnico", "post_count": 3},
        {"register": "ironico", "post_count": 3},
        {"register": "pedagogico", "post_count": 1},
    ])
    result = await svc.register_distribution(days=30)
    assert result.total_posts == 10
    assert result.alert is False
    assert result.dominant_register == "analitico"
    assert len(result.slices) == 4
    # percentages sum to 100
    assert sum(s.pct for s in result.slices) == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_distribution_alert_when_over_40pct(repo_and_service):
    _, conn, svc = repo_and_service
    conn.fetch = AsyncMock(return_value=[
        {"register": "ironico", "post_count": 5},  # 50%
        {"register": "tecnico", "post_count": 5},
    ])
    result = await svc.register_distribution(days=30)
    assert result.alert is True
    assert result.dominant_register == "ironico"


@pytest.mark.asyncio
async def test_distribution_empty_no_alert_no_dominant(repo_and_service):
    _, conn, svc = repo_and_service
    conn.fetch = AsyncMock(return_value=[])
    result = await svc.register_distribution(days=30)
    assert result.total_posts == 0
    assert result.alert is False
    assert result.dominant_register is None
    assert result.slices == []


# ── 4. Funnel ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_funnel_stages_ordered(repo_and_service):
    _, conn, svc = repo_and_service
    conn.fetchrow = AsyncMock(side_effect=[
        {"n": 20},  # drafts
        {"n": 15},  # approved
        {"n": 12},  # published
        {"n": 3},   # leads
    ])
    stages = await svc.funnel(days=30)
    assert [s.stage for s in stages] == [
        "drafts", "approved", "published", "leads",
    ]
    assert [s.count for s in stages] == [20, 15, 12, 3]


@pytest.mark.asyncio
async def test_funnel_handles_empty(repo_and_service):
    _, conn, svc = repo_and_service
    conn.fetchrow = AsyncMock(return_value=None)
    stages = await svc.funnel(days=30)
    assert all(s.count == 0 for s in stages)


# ── 5. Rejections ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rejections_sorted_desc(repo_and_service):
    _, conn, svc = repo_and_service
    conn.fetch = AsyncMock(return_value=[
        {"reason": "tone", "n": 5},
        {"reason": "clickbait", "n": 3},
    ])
    buckets = await svc.rejection_reasons(days=30)
    assert [b.reason for b in buckets] == ["tone", "clickbait"]
    assert [b.count for b in buckets] == [5, 3]


# ── 6. Costs ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cost_per_draft(repo_and_service):
    _, conn, svc = repo_and_service
    did = uuid4()
    conn.fetch = AsyncMock(return_value=[
        {
            "draft_id": did,
            "topic": "Permenkumham 22/2023",
            "total_usd": Decimal("0.16"),
            "by_type": {"imagen_ultra": Decimal("0.06"), "imagen_fast": Decimal("0.10")},
        },
    ])
    rows = await svc.cost_per_draft(days=30, limit=10)
    assert len(rows) == 1
    d = rows[0].to_dict()
    assert d["draft_id"] == str(did)
    assert d["total_usd"] == 0.16
    assert d["by_type"] == {"imagen_ultra": 0.06, "imagen_fast": 0.1}


@pytest.mark.asyncio
async def test_cost_per_draft_handles_jsonb_string(repo_and_service):
    """PG returns jsonb as str when asyncpg doesn't register a codec — tolerate."""
    _, conn, svc = repo_and_service
    did = uuid4()
    conn.fetch = AsyncMock(return_value=[
        {
            "draft_id": did,
            "topic": "t",
            "total_usd": Decimal("0.03"),
            "by_type": '{"fireworks_flux": 0.03}',
        },
    ])
    rows = await svc.cost_per_draft(days=30)
    assert rows[0].by_type == {"fireworks_flux": 0.03}


@pytest.mark.asyncio
async def test_cost_per_draft_empty_by_type(repo_and_service):
    _, conn, svc = repo_and_service
    conn.fetch = AsyncMock(return_value=[
        {
            "draft_id": uuid4(),
            "topic": "t",
            "total_usd": Decimal("0.01"),
            "by_type": None,
        },
    ])
    rows = await svc.cost_per_draft(days=30)
    assert rows[0].by_type == {}


# ── Constants sanity ─────────────────────────────────────────


def test_pie_alert_threshold_at_40():
    assert PIE_DOMINANCE_ALERT_PCT == 40.0
