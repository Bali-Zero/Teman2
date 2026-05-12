"""Phase 3 TICKET B EXECUTION — cell_post_emit integration tests.

6 unit tests + 4 _extract_source schema-drift tests covering:
- _build_hgt_bridge success path (XLEN=18 → bridge instantiated)
- _build_hgt_bridge failure path (XLEN<18 → returns None, client closed)
- emit_pipeline_run no-bridge no-op
- emit_pipeline_run no-articles skip with state-keys log
- emit_pipeline_run publishes pattern above threshold (≥3 articles/source)
- _extract_source schema-drift fallback chain (4 sub-tests)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_PACKAGE_PATH = Path(__file__).resolve().parents[2]
if str(_PACKAGE_PATH) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PATH))

from backend.cell.cell_post_emit import (  # noqa: E402
    _build_hgt_bridge,
    _extract_source,
    emit_pipeline_run,
)


@pytest.mark.asyncio
async def test_build_hgt_bridge_succeeds_with_seed_signature() -> None:
    """XLEN cell:skills returns 18 → bridge instantiated, no exception."""
    import redis.asyncio as redis_async

    mock_client = AsyncMock()
    mock_client.xlen = AsyncMock(return_value=18)

    mock_bridge = MagicMock()

    with (
        patch.object(redis_async, "from_url", return_value=mock_client),
        patch(
            "backend.cell.hgt_publisher.IntelScraperHGTBridge.from_redis",
            return_value=mock_bridge,
        ),
    ):
        bridge = await _build_hgt_bridge()

    assert bridge is mock_bridge
    mock_client.xlen.assert_awaited_once_with("cell:skills")


@pytest.mark.asyncio
async def test_build_hgt_bridge_fails_below_seed() -> None:
    """XLEN cell:skills returns 0 → returns None + closes client."""
    import redis.asyncio as redis_async

    mock_client = AsyncMock()
    mock_client.xlen = AsyncMock(return_value=0)
    mock_client.aclose = AsyncMock()

    with patch.object(redis_async, "from_url", return_value=mock_client):
        bridge = await _build_hgt_bridge()

    assert bridge is None
    mock_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_emit_pipeline_run_no_bridge_is_noop() -> None:
    """bridge=None → emit_pipeline_run returns silently, no exception."""
    with patch(
        "backend.cell.cell_post_emit._build_hgt_bridge",
        return_value=None,
    ):
        # Should NOT raise
        await emit_pipeline_run({"run_id": "test", "articles": []})


@pytest.mark.asyncio
async def test_emit_pipeline_run_no_articles_skips() -> None:
    """Empty articles list → log info + return without exception."""
    mock_bridge = AsyncMock()
    mock_bridge.publish = AsyncMock(return_value=True)

    with patch(
        "backend.cell.cell_post_emit._build_hgt_bridge",
        return_value=mock_bridge,
    ):
        await emit_pipeline_run({"run_id": "t1", "articles": []})

    mock_bridge.publish.assert_not_called()


@pytest.mark.asyncio
async def test_emit_pipeline_run_publishes_pattern_above_threshold() -> None:
    """≥3 articles from same source → bridge.publish called with canonical pattern."""
    mock_bridge = AsyncMock()
    mock_bridge.publish = AsyncMock(return_value=True)

    state = {
        "run_id": "20260513_010000",
        "articles": [
            {"source_name": "djp.go.id", "title": "a1"},
            {"source_name": "djp.go.id", "title": "a2"},
            {"source_name": "djp.go.id", "title": "a3"},
            {"source_name": "imigrasi.go.id", "title": "b1"},
            {"source_name": "imigrasi.go.id", "title": "b2"},
        ],
    }

    with patch(
        "backend.cell.cell_post_emit._build_hgt_bridge",
        return_value=mock_bridge,
    ):
        await emit_pipeline_run(state)

    # djp.go.id has 3 articles (≥3 threshold), imigrasi.go.id has only 2
    mock_bridge.publish.assert_awaited_once()
    pattern = mock_bridge.publish.call_args[0][0]
    assert pattern.pattern_id == "rss_feed_stable_djp.go.id_20260513_010000"
    assert pattern.source == "djp.go.id"
    assert "djp.go.id" in pattern.procedure
    assert "3" in pattern.procedure  # article_count in message
    assert pattern.confidence == 0.8
    assert pattern.domain == "news"
    assert pattern.precondition == "nightly intel-scraper crawl"


def test_extract_source_schema_drift_primary_source_name() -> None:
    """source_name takes precedence over source and url."""
    assert _extract_source({"source_name": "a", "source": "b", "url": "c"}) == "a"


def test_extract_source_schema_drift_fallback_source() -> None:
    """source used when source_name absent."""
    assert _extract_source({"source": "b", "url": "c"}) == "b"


def test_extract_source_schema_drift_fallback_url() -> None:
    """url used when source_name and source absent."""
    assert _extract_source({"url": "c"}) == "c"


def test_extract_source_schema_drift_fallback_unknown() -> None:
    """unknown literal returned when all fields absent."""
    assert _extract_source({}) == "unknown"
