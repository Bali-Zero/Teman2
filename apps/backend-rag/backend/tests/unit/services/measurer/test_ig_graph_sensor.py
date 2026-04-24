"""Tests for IGGraphSensor — own account metrics pull via Graph API v20."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from backend.services.measurer.ig_graph_sensor import (
    IGGraphSensor,
    IGGraphError,
    IGPostMetrics,
)


@pytest.mark.asyncio
async def test_read_returns_followers_and_post_count():
    sensor = IGGraphSensor(token="tok", ig_user_id="123", http_client=None)
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {
        "followers_count": 5123,
        "media_count": 245,
        "biography": "Bali Zero",
    }
    with patch.object(sensor, "_get", AsyncMock(return_value=mock_resp.json())):
        result = await sensor.read_account_summary()
    assert result["followers_count"] == 5123
    assert result["media_count"] == 245


@pytest.mark.asyncio
async def test_read_posts_returns_last_n_with_insights():
    sensor = IGGraphSensor(token="tok", ig_user_id="123", http_client=None)
    media_page = {
        "data": [
            {
                "id": "m1",
                "caption": "Hook line one\nBody",
                "media_type": "CAROUSEL_ALBUM",
                "timestamp": "2026-04-20T03:00:00+0000",
                "permalink": "https://instagram.com/p/ABC",
            }
        ]
    }
    insights = {
        "data": [
            {"name": "likes", "values": [{"value": 120}]},
            {"name": "comments", "values": [{"value": 8}]},
            {"name": "saved", "values": [{"value": 34}]},
            {"name": "reach", "values": [{"value": 2100}]},
        ]
    }

    async def fake_get(path: str, **kw):
        if "/media" in path and "/insights" not in path:
            return media_page
        if "/insights" in path:
            return insights
        raise AssertionError(f"unexpected path {path}")

    with patch.object(sensor, "_get", side_effect=fake_get):
        posts = await sensor.read_posts(limit=1)

    assert len(posts) == 1
    p = posts[0]
    assert isinstance(p, IGPostMetrics)
    assert p.post_id == "m1"
    assert p.format == "CAROUSEL_ALBUM"
    assert p.likes == 120
    assert p.saves == 34
    assert p.reach == 2100
    assert "Hook line one" in p.caption


@pytest.mark.asyncio
async def test_raises_on_graph_api_error():
    sensor = IGGraphSensor(token="tok", ig_user_id="123", http_client=None)

    async def fake_get(path, **kw):
        return {"error": {"message": "rate limit", "code": 4}}

    with patch.object(sensor, "_get", side_effect=fake_get):
        with pytest.raises(IGGraphError, match="rate limit"):
            await sensor.read_account_summary()
