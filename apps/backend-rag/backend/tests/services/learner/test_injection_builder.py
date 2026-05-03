"""Tests for MemoriaEpisodicaBuilder — 2000-char cap + content assembly."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.learner.injection_builder import (
    BLOCK_CLOSE,
    BLOCK_OPEN,
    MAX_BLOCK_CHARS,
    MemoriaEpisodicaBuilder,
)
from backend.services.war_room.models import (
    RejectedBy,
    RejectionReason,
    WarRoomRejection,
)


def _rej(reason: RejectionReason) -> WarRoomRejection:
    return WarRoomRejection(
        id=uuid4(),
        draft_id=uuid4(),
        reason=reason,
        reason_detail=None,
        rejected_by=RejectedBy.ZERO,
        rejected_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def repo():
    m = AsyncMock()
    m.recent_rejections = AsyncMock(return_value=[])
    return m


# ── Empty state ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_block_with_empty_message_when_no_data(repo):
    b = MemoriaEpisodicaBuilder(repo=repo)
    out = await b.build()
    assert out.startswith(BLOCK_OPEN)
    assert out.endswith(BLOCK_CLOSE)
    assert "nessuna memoria episodica" in out


# ── Skill / rejection / performance assembly ──────────────────


@pytest.mark.asyncio
async def test_includes_all_three_sections(repo):
    repo.recent_rejections = AsyncMock(return_value=[
        _rej(RejectionReason.TONE),
        _rej(RejectionReason.TONE),
        _rej(RejectionReason.CLICKBAIT),
    ])

    async def skill_search(query, limit):
        return [
            {"name": "war_room:analitico:ig:abc", "confidence": 0.82,
             "procedure": "prefer analitico on visa topics"},
            {"name": "war_room:tecnico:linkedin:xyz", "confidence": 0.7,
             "procedure": "deep-dive Permenkumham works on LI"},
        ]

    async def council_perf():
        return [
            {
                "register": "analitico",
                "last_14d_posts": 4,
                "avg_composite_score": 0.78,
                "top_topic": "B211A",
            },
            {
                "register": "tecnico",
                "last_14d_posts": 2,
                "avg_composite_score": 0.65,
                "top_topic": "LKPM",
            },
        ]

    b = MemoriaEpisodicaBuilder(
        repo=repo,
        skill_search_fn=skill_search,
        council_performance_fn=council_perf,
    )
    out = await b.build()
    assert "Skills recenti" in out
    assert "war_room:analitico:ig:abc" in out
    assert "Rifiuti ultimi 14gg" in out
    assert "tone: 2" in out
    assert "clickbait: 1" in out
    assert "Performance per registro" in out
    assert "analitico" in out
    assert "B211A" in out


@pytest.mark.asyncio
async def test_skills_limited_to_five(repo):
    async def skill_search(query, limit):
        return [
            {"name": f"skill:{i}", "confidence": 0.8, "procedure": f"proc {i}"}
            for i in range(10)
        ]

    b = MemoriaEpisodicaBuilder(repo=repo, skill_search_fn=skill_search)
    out = await b.build()
    # only first 5 skills rendered
    assert "skill:0" in out
    assert "skill:4" in out
    assert "skill:5" not in out


# ── Length cap ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_block_never_exceeds_2000_chars(repo):
    async def skill_search(query, limit):
        return [
            {
                "name": f"skill_id_with_long_name_{i}",
                "confidence": 0.7,
                "procedure": "x" * 500,  # intentionally long
            }
            for i in range(5)
        ]

    b = MemoriaEpisodicaBuilder(repo=repo, skill_search_fn=skill_search)
    out = await b.build()
    assert len(out) <= MAX_BLOCK_CHARS
    assert out.startswith(BLOCK_OPEN)
    assert out.endswith(BLOCK_CLOSE)


@pytest.mark.asyncio
async def test_truncation_keeps_ellipsis_inside_block(repo):
    async def skill_search(query, limit):
        return [
            {"name": "s", "confidence": 0.9, "procedure": "y" * 5000},
        ]

    b = MemoriaEpisodicaBuilder(repo=repo, skill_search_fn=skill_search)
    out = await b.build()
    inner = out[len(BLOCK_OPEN):-len(BLOCK_CLOSE)].strip()
    assert inner.endswith("…") or not inner.endswith("…") and len(out) <= MAX_BLOCK_CHARS
    # block tags still intact
    assert out.startswith(BLOCK_OPEN)
    assert out.endswith(BLOCK_CLOSE)


# ── Error resilience ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_skill_search_failure_doesnt_crash_build(repo):
    async def broken(query, limit):
        raise RuntimeError("genome offline")

    b = MemoriaEpisodicaBuilder(repo=repo, skill_search_fn=broken)
    out = await b.build()
    # no skills section, but block still renders
    assert out.startswith(BLOCK_OPEN)


@pytest.mark.asyncio
async def test_rejections_failure_doesnt_crash_build(repo):
    repo.recent_rejections = AsyncMock(side_effect=RuntimeError("pg down"))
    b = MemoriaEpisodicaBuilder(repo=repo)
    out = await b.build()
    assert out.startswith(BLOCK_OPEN)
    assert "Rifiuti ultimi 14gg" not in out


@pytest.mark.asyncio
async def test_performance_failure_doesnt_crash_build(repo):
    async def broken():
        raise RuntimeError("view missing")

    b = MemoriaEpisodicaBuilder(repo=repo, council_performance_fn=broken)
    out = await b.build()
    assert out.startswith(BLOCK_OPEN)
    assert "Performance per registro" not in out
