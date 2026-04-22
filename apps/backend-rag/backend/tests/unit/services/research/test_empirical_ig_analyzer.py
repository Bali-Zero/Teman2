"""Tests for empirical_ig_analyzer — loads + will classify 25 own posts."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from backend.services.research.empirical_ig_analyzer import (
    EmpiricalIGAnalyzer,
    ClassifiedPost,
)


@pytest.mark.asyncio
async def test_load_posts_excludes_last_4():
    """Spec requires posts 5-29 (last 4 too recent for mature engagement)."""
    mock_sensor = AsyncMock()
    fake_posts = [{"post_id": f"p{i}", "likes": 10} for i in range(1, 30)]
    mock_sensor.read_posts.return_value = fake_posts
    analyzer = EmpiricalIGAnalyzer(ig_sensor=mock_sensor)
    loaded = await analyzer.load_posts_for_analysis()
    assert len(loaded) == 25
    assert loaded[0]["post_id"] == "p5"  # first post is the 5th newest
    assert loaded[-1]["post_id"] == "p29"


@pytest.mark.asyncio
async def test_load_posts_handles_short_account():
    """If account has fewer than 29 posts, skip 4 newest and return the rest."""
    mock_sensor = AsyncMock()
    fake_posts = [{"post_id": f"p{i}"} for i in range(1, 11)]  # 10 posts
    mock_sensor.read_posts.return_value = fake_posts
    analyzer = EmpiricalIGAnalyzer(ig_sensor=mock_sensor)
    loaded = await analyzer.load_posts_for_analysis()
    assert len(loaded) == 6  # 10 - 4 newest
    assert loaded[0]["post_id"] == "p5"


@pytest.mark.asyncio
async def test_load_posts_returns_empty_when_too_few():
    """If account has <= 4 posts, return empty list."""
    mock_sensor = AsyncMock()
    mock_sensor.read_posts.return_value = [{"post_id": "p1"}, {"post_id": "p2"}]
    analyzer = EmpiricalIGAnalyzer(ig_sensor=mock_sensor)
    loaded = await analyzer.load_posts_for_analysis()
    assert loaded == []


def test_classified_post_schema_has_all_attrs():
    cp = ClassifiedPost(
        post_id="p5", caption="Hook one\nBody here",
        format="CAROUSEL_ALBUM", hook_type="question",
        tone_register="pedagogico", topic="visa",
        posted_hour_wita=12, likes=100, comments=5, saves=20, reach=1500,
    )
    assert cp.engagement_rate == pytest.approx((100 + 5 + 20) / 1500, rel=0.01)


def test_classified_post_engagement_rate_zero_reach():
    cp = ClassifiedPost(
        post_id="p5", caption="x", format="IMAGE", hook_type="question",
        tone_register="tecnico", topic="tax", posted_hour_wita=10,
        likes=5, comments=0, saves=1, reach=0,
    )
    assert cp.engagement_rate == 0.0
