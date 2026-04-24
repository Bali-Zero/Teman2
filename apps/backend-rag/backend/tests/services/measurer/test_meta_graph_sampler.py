"""Tests for MetaGraphSampler (mocked httpx)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from backend.services.measurer.base import (
    METRIC_COMMENTS,
    METRIC_IMPRESSIONS,
    METRIC_LIKES,
    METRIC_REACH,
    METRIC_SAVES,
    METRIC_SHARES,
    SamplerError,
)
from backend.services.measurer.meta_graph_sampler import (
    MetaGraphSampler,
    _parse_insights,
)
from backend.services.war_room.models import (
    MetricSource,
    Platform,
    WarRoomPost,
)


def _ok(data: list[dict]) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = 200
    r.json.return_value = {"data": data}
    r.text = str(data)
    return r


def _err(status: int, text: str = "error") -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = text
    return r


def _post(platform: Platform = Platform.INSTAGRAM, ext: str | None = "ig-17") -> WarRoomPost:
    return WarRoomPost(
        id=uuid4(),
        draft_id=uuid4(),
        platform=platform,
        post_external_id=ext,
        tone_register=None,
        published_at=datetime.now(timezone.utc),
    )


# ── Config ────────────────────────────────────────────────────


def test_requires_token(monkeypatch):
    # MetaGraphSampler.__init__ accepts either IG_LONG_LIVED_TOKEN (preferred)
    # or INSTAGRAM_ACCESS_TOKEN (fallback). Must clear both — another test
    # module (backend/tests/unit/services/integrations/test_instagram_service.py:25)
    # does `os.environ.setdefault("INSTAGRAM_ACCESS_TOKEN", ...)` at import
    # time, which survives for the rest of the pytest session once that module
    # loads. Only deleting IG_LONG_LIVED_TOKEN would leave the fallback wired
    # up and no SamplerError would be raised.
    monkeypatch.delenv("IG_LONG_LIVED_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    with pytest.raises(SamplerError):
        MetaGraphSampler()


def test_sampler_supports_only_instagram():
    s = MetaGraphSampler(access_token="t")
    assert s.supports(Platform.INSTAGRAM) is True
    assert s.supports(Platform.X) is False


# ── _parse_insights ──────────────────────────────────────────


def test_parse_insights_full_payload():
    data = [
        {"name": "reach", "values": [{"value": 12000}]},
        {"name": "impressions", "values": [{"value": 15000}]},
        {"name": "saved", "values": [{"value": 85}]},
        {"name": "shares", "values": [{"value": 30}]},
        {"name": "likes", "values": [{"value": 500}]},
        {"name": "comments", "values": [{"value": 42}]},
    ]
    out = _parse_insights({"data": data})
    names = {d.metric_name for d in out}
    # 'saved' maps to saves canonical name
    assert names == {
        METRIC_REACH, METRIC_IMPRESSIONS, METRIC_SAVES,
        METRIC_SHARES, METRIC_LIKES, METRIC_COMMENTS,
    }
    reach = next(d for d in out if d.metric_name == METRIC_REACH)
    assert reach.value == 12000.0
    assert reach.source == MetricSource.META_GRAPH


def test_parse_insights_handles_empty():
    assert _parse_insights({}) == []
    assert _parse_insights({"data": []}) == []


def test_parse_insights_skips_unknown_metric():
    data = [
        {"name": "reach", "values": [{"value": 1}]},
        {"name": "profile_visits", "values": [{"value": 7}]},  # not in map
    ]
    out = _parse_insights({"data": data})
    assert len(out) == 1
    assert out[0].metric_name == METRIC_REACH


def test_parse_insights_skips_non_numeric():
    data = [
        {"name": "reach", "values": [{"value": "bad"}]},
        {"name": "likes", "values": [{"value": 42}]},
    ]
    out = _parse_insights({"data": data})
    assert [d.metric_name for d in out] == [METRIC_LIKES]


def test_parse_insights_skips_malformed_entry():
    data = [
        "not a dict",
        {"name": "likes"},                         # no values
        {"name": "likes", "values": []},          # empty values
        {"name": "likes", "values": [{"value": 1}]},
    ]
    out = _parse_insights({"data": data})
    assert len(out) == 1


# ── sample ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sample_happy_path():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_ok([
        {"name": "reach", "values": [{"value": 1200}]},
        {"name": "impressions", "values": [{"value": 1500}]},
        {"name": "saved", "values": [{"value": 45}]},
        {"name": "shares", "values": [{"value": 20}]},
        {"name": "likes", "values": [{"value": 120}]},
        {"name": "comments", "values": [{"value": 18}]},
    ]))
    s = MetaGraphSampler(access_token="t", http_client=client)
    result = await s.sample(_post())
    assert result.ok is True
    assert result.partial is False
    assert len(result.data) == 6


@pytest.mark.asyncio
async def test_sample_partial_when_fewer_metrics_returned():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_ok([
        {"name": "reach", "values": [{"value": 1000}]},
    ]))
    s = MetaGraphSampler(access_token="t", http_client=client)
    result = await s.sample(_post())
    assert result.ok is True
    assert result.partial is True
    assert len(result.data) == 1


@pytest.mark.asyncio
async def test_sample_http_error_returns_not_ok():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_err(403, "forbidden"))
    s = MetaGraphSampler(access_token="t", http_client=client)
    result = await s.sample(_post())
    assert result.ok is False
    assert "403" in (result.error or "")


@pytest.mark.asyncio
async def test_sample_wrong_platform_rejected():
    s = MetaGraphSampler(access_token="t")
    result = await s.sample(_post(platform=Platform.X))
    assert result.ok is False
    assert "external id" in (result.error or "")


@pytest.mark.asyncio
async def test_sample_exception_wrapped():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("down"))
    s = MetaGraphSampler(access_token="t", http_client=client)
    result = await s.sample(_post())
    assert result.ok is False
    assert "ConnectError" in (result.error or "")
