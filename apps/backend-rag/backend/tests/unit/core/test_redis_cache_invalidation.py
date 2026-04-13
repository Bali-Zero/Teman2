"""
Unit tests for Redis event-driven cache invalidation methods.

Tests invalidate_by_pattern, invalidate_collection_cache, invalidate_session_cache,
invalidate_faq_cache, and get_redis_memory_info in RedisManager.

All Redis connections are mocked to avoid requiring a live Redis server.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis_manager import RedisManager


class TestInvalidateByPattern:
    """Tests for RedisManager.invalidate_by_pattern()."""

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    @pytest.mark.asyncio
    async def test_invalidate_by_pattern_deletes_matching_keys(self) -> None:
        """SCAN finds keys, DELETE removes them."""
        mgr = RedisManager()
        mock_client = AsyncMock()
        # First SCAN returns keys, second returns cursor=0 (done)
        mock_client.scan.side_effect = [
            (42, ["zantara:hybrid_search:visa_oracle:q1", "zantara:hybrid_search:visa_oracle:q2"]),
            (0, []),
        ]
        mock_client.delete.return_value = 2
        mgr._async_client = mock_client
        mgr._available = True

        deleted = await mgr.invalidate_by_pattern("zantara:hybrid_search:visa_oracle:*")

        assert deleted == 2
        mock_client.scan.assert_called()
        mock_client.delete.assert_called_once_with(
            "zantara:hybrid_search:visa_oracle:q1",
            "zantara:hybrid_search:visa_oracle:q2",
        )

    @pytest.mark.asyncio
    async def test_invalidate_by_pattern_no_matching_keys(self) -> None:
        """SCAN returns no keys — nothing to delete."""
        mgr = RedisManager()
        mock_client = AsyncMock()
        mock_client.scan.return_value = (0, [])
        mgr._async_client = mock_client
        mgr._available = True

        deleted = await mgr.invalidate_by_pattern("zantara:nonexistent:*")

        assert deleted == 0
        mock_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_by_pattern_redis_unavailable(self) -> None:
        """Returns 0 when Redis is not available."""
        mgr = RedisManager()
        mgr._available = False
        mgr._async_client = None

        deleted = await mgr.invalidate_by_pattern("zantara:*")

        assert deleted == 0

    @pytest.mark.asyncio
    async def test_invalidate_by_pattern_handles_redis_error(self) -> None:
        """Returns 0 and logs error on Redis failure."""
        mgr = RedisManager()
        mock_client = AsyncMock()
        mock_client.scan.side_effect = ConnectionError("Redis gone")
        mgr._async_client = mock_client
        mgr._available = True

        deleted = await mgr.invalidate_by_pattern("zantara:*")

        assert deleted == 0


class TestInvalidateCollectionCache:
    """Tests for RedisManager.invalidate_collection_cache()."""

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    @pytest.mark.asyncio
    async def test_invalidates_hybrid_and_search_patterns(self) -> None:
        """Should invalidate both hybrid_search and search patterns for a collection."""
        mgr = RedisManager()
        mock_client = AsyncMock()

        # Track which patterns are scanned
        scan_results: dict[str, list[str]] = {
            "zantara:hybrid_search:visa_oracle:*": ["zantara:hybrid_search:visa_oracle:abc"],
            "zantara:search:visa_oracle:*": ["zantara:search:visa_oracle:def"],
        }

        async def mock_scan(cursor: int = 0, match: str = "*", count: int = 100) -> tuple[int, list[str]]:
            keys = scan_results.get(match, [])
            # Return keys on first scan, empty on subsequent
            if keys and match in scan_results:
                result = list(keys)
                scan_results[match] = []  # Clear so next call returns empty
                return (0, result)
            return (0, [])

        mock_client.scan = mock_scan
        mock_client.delete = AsyncMock(return_value=1)
        mgr._async_client = mock_client
        mgr._available = True

        deleted = await mgr.invalidate_collection_cache("visa_oracle")

        assert deleted == 2  # 1 from hybrid_search + 1 from search
        assert mock_client.delete.call_count == 2


class TestInvalidateSessionCache:
    """Tests for RedisManager.invalidate_session_cache()."""

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    @pytest.mark.asyncio
    async def test_invalidates_specific_session(self) -> None:
        """Should target a specific session ID."""
        mgr = RedisManager()
        mock_client = AsyncMock()
        mock_client.scan.return_value = (0, ["zantara:session:sess123:data"])
        mock_client.delete.return_value = 1
        mgr._async_client = mock_client
        mgr._available = True

        deleted = await mgr.invalidate_session_cache(session_id="sess123")

        assert deleted == 1
        mock_client.scan.assert_called_once_with(
            cursor=0, match="zantara:session:sess123:*", count=100,
        )

    @pytest.mark.asyncio
    async def test_invalidates_all_sessions(self) -> None:
        """Without session_id, invalidate all session keys."""
        mgr = RedisManager()
        mock_client = AsyncMock()
        mock_client.scan.return_value = (0, ["zantara:session:a:data", "zantara:session:b:data"])
        mock_client.delete.return_value = 2
        mgr._async_client = mock_client
        mgr._available = True

        deleted = await mgr.invalidate_session_cache()

        assert deleted == 2
        mock_client.scan.assert_called_once_with(
            cursor=0, match="zantara:session:*", count=100,
        )


class TestInvalidateFaqCache:
    """Tests for RedisManager.invalidate_faq_cache()."""

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    @pytest.mark.asyncio
    async def test_invalidates_faq_keys(self) -> None:
        mgr = RedisManager()
        mock_client = AsyncMock()
        mock_client.scan.return_value = (0, ["zantara:faq:visa", "zantara:faq:tax"])
        mock_client.delete.return_value = 2
        mgr._async_client = mock_client
        mgr._available = True

        deleted = await mgr.invalidate_faq_cache()

        assert deleted == 2


class TestGetRedisMemoryInfo:
    """Tests for RedisManager.get_redis_memory_info()."""

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    @pytest.mark.asyncio
    async def test_returns_memory_stats(self) -> None:
        mgr = RedisManager()
        mock_client = AsyncMock()
        mock_client.info.side_effect = [
            # memory info
            {
                "used_memory": 1048576,
                "used_memory_human": "1.00M",
                "maxmemory": 268435456,
                "maxmemory_human": "256.00M",
                "maxmemory_policy": "allkeys-lru",
            },
            # stats info
            {"evicted_keys": 42},
            # clients info
            {"connected_clients": 5},
        ]
        mgr._async_client = mock_client
        mgr._available = True

        with patch("backend.app.metrics.metrics_collector") as mock_metrics:
            info = await mgr.get_redis_memory_info()

        assert info["used_memory"] == 1048576
        assert info["used_memory_human"] == "1.00M"
        assert info["maxmemory"] == 268435456
        assert info["maxmemory_policy"] == "allkeys-lru"
        assert info["evicted_keys"] == 42
        assert info["connected_clients"] == 5

    @pytest.mark.asyncio
    async def test_returns_defaults_when_unavailable(self) -> None:
        mgr = RedisManager()
        mgr._available = False
        mgr._async_client = None

        info = await mgr.get_redis_memory_info()

        assert info["used_memory"] == 0
        assert info["error"] == "Redis unavailable"

    @pytest.mark.asyncio
    async def test_handles_info_failure(self) -> None:
        mgr = RedisManager()
        mock_client = AsyncMock()
        mock_client.info.side_effect = ConnectionError("Redis gone")
        mgr._async_client = mock_client
        mgr._available = True

        info = await mgr.get_redis_memory_info()

        assert "error" in info
        assert info["used_memory"] == 0
