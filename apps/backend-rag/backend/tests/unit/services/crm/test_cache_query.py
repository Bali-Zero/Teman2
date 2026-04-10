"""Tests for backend.services.crm.cache_query"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.crm.cache_query import (
    CRMCache,
    CRMQueryOptimizer,
    QueryCache,
    cache_crm_result,
    health_check_crm_tables,
)


# ── CRMCache ────────────────────────────────────────────────────────────────


class TestCRMCache:
    @pytest.fixture
    def cache(self):
        return CRMCache(default_ttl=300)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing_key(self, cache):
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_expired_key(self, cache):
        await cache.set("expired", "data", ttl=0)
        # Force expiry by manipulating cache entry
        cache._cache["expired"] = ("data", datetime.now(timezone.utc) - timedelta(seconds=1))
        result = await cache.get("expired")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        await cache.set("del_key", "val")
        await cache.delete("del_key")
        result = await cache.get("del_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache):
        await cache.delete("doesnt_exist")  # Should not raise

    @pytest.mark.asyncio
    async def test_clear_pattern(self, cache):
        await cache.set("client:1:data", "a")
        await cache.set("client:1:name", "b")
        await cache.set("practice:5:data", "c")

        count = await cache.clear_pattern("client:1")
        assert count == 2
        assert await cache.get("client:1:data") is None
        assert await cache.get("practice:5:data") == "c"

    @pytest.mark.asyncio
    async def test_clear_all(self, cache):
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.clear()
        assert await cache.get("a") is None
        assert await cache.get("b") is None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache):
        await cache.set("fresh", "ok")
        cache._cache["stale"] = ("old", datetime.now(timezone.utc) - timedelta(seconds=10))
        count = await cache.cleanup_expired()
        assert count == 1
        assert await cache.get("fresh") == "ok"
        assert await cache.get("stale") is None

    @pytest.mark.asyncio
    async def test_custom_ttl(self, cache):
        await cache.set("custom", "val", ttl=600)
        result = await cache.get("custom")
        assert result == "val"


# ── cache_crm_result decorator ──────────────────────────────────────────────


class TestCacheCrmResult:
    @pytest.mark.asyncio
    async def test_caches_result(self):
        call_count = 0

        @cache_crm_result(ttl=60, key_prefix="test")
        async def expensive_fn(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # Import the singleton to clear it first
        from backend.services.crm.cache_query import crm_cache
        await crm_cache.clear()

        r1 = await expensive_fn(5)
        r2 = await expensive_fn(5)
        assert r1 == 10
        assert r2 == 10
        assert call_count == 1  # second call hits cache


# ── QueryCache ──────────────────────────────────────────────────────────────


class TestQueryCache:
    @pytest.fixture
    def qcache(self):
        return QueryCache()

    @pytest.mark.asyncio
    async def test_client_by_email_set_get(self, qcache):
        await qcache.set_client_by_email("test@example.com", 42)
        result = await qcache.get_client_by_email("test@example.com")
        assert result == 42

    @pytest.mark.asyncio
    async def test_client_by_email_missing(self, qcache):
        result = await qcache.get_client_by_email("missing@example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_client_by_email_expired(self, qcache):
        await qcache.set_client_by_email("exp@example.com", 1, ttl=0)
        qcache._client_by_email["exp@example.com"] = (
            1,
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        result = await qcache.get_client_by_email("exp@example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_client_by_phone_set_get(self, qcache):
        with patch(
            "backend.services.crm.cache_query.QueryCache._normalize_phone",
            return_value="+628123456",
        ):
            await qcache.set_client_by_phone("+628123456", 99)
            result = await qcache.get_client_by_phone("+628123456")
            assert result == 99

    @pytest.mark.asyncio
    async def test_client_by_phone_missing(self, qcache):
        with patch(
            "backend.services.crm.cache_query.QueryCache._normalize_phone",
            return_value="+62000",
        ):
            result = await qcache.get_client_by_phone("+62000")
            assert result is None

    @pytest.mark.asyncio
    async def test_practice_types_set_get(self, qcache):
        types = [{"id": 1, "name": "KITAS"}]
        await qcache.set_practice_types(types)
        result = await qcache.get_practice_types()
        assert result == types

    @pytest.mark.asyncio
    async def test_practice_types_not_set(self, qcache):
        result = await qcache.get_practice_types()
        assert result is None

    @pytest.mark.asyncio
    async def test_practice_types_expired(self, qcache):
        await qcache.set_practice_types([{"id": 1}])
        qcache._practice_types_updated = datetime.now(timezone.utc) - timedelta(hours=2)
        result = await qcache.get_practice_types()
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_client(self, qcache):
        await qcache.set_client_by_email("alice@example.com", 42)
        with patch(
            "backend.services.crm.cache_query.QueryCache._normalize_phone",
            return_value="+62111",
        ):
            await qcache.set_client_by_phone("+62111", 42)
            await qcache.invalidate_client(42)
            assert await qcache.get_client_by_email("alice@example.com") is None
            assert await qcache.get_client_by_phone("+62111") is None


# ── CRMQueryOptimizer ───────────────────────────────────────────────────────


def _make_pool_with_conn(mock_conn):
    """Create a mock pool that works with `async with pool.acquire() as conn:` and `conn.transaction()`."""
    mock_pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = ctx
    # conn.transaction() must return sync context manager (not coroutine)
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=None)
    tx_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=tx_ctx)
    return mock_pool


class TestCRMQueryOptimizer:
    @pytest.mark.asyncio
    async def test_batch_insert_empty(self):
        mock_pool = _make_pool_with_conn(AsyncMock())
        optimizer = CRMQueryOptimizer(db_pool=mock_pool)
        result = await optimizer.batch_insert_clients([])
        assert result == []

    @pytest.mark.asyncio
    async def test_batch_insert_clients(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        mock_pool = _make_pool_with_conn(mock_conn)
        optimizer = CRMQueryOptimizer(db_pool=mock_pool)

        clients = [
            {"full_name": "John", "email": "john@example.com"},
            {"full_name": "Jane", "email": "jane@example.com"},
        ]
        result = await optimizer.batch_insert_clients(clients)
        assert result == [1, 2]

    @pytest.mark.asyncio
    async def test_batch_update_empty(self):
        mock_pool = _make_pool_with_conn(AsyncMock())
        optimizer = CRMQueryOptimizer(db_pool=mock_pool)
        result = await optimizer.batch_update_practices([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_batch_update_disallowed_column(self):
        mock_conn = AsyncMock()
        mock_pool = _make_pool_with_conn(mock_conn)
        optimizer = CRMQueryOptimizer(db_pool=mock_pool)

        with pytest.raises(ValueError, match="not allowed"):
            await optimizer.batch_update_practices([
                {"id": 1, "malicious_column": "DROP TABLE"},
            ])

    @pytest.mark.asyncio
    async def test_get_clients_with_practices_empty(self):
        mock_pool = _make_pool_with_conn(AsyncMock())
        optimizer = CRMQueryOptimizer(db_pool=mock_pool)
        result = await optimizer.get_clients_with_practices([])
        assert result == []

    @pytest.mark.asyncio
    async def test_search_clients_optimized(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"full_name": "John", "email": "john@test.com", "total_count": 1},
        ])

        mock_pool = _make_pool_with_conn(mock_conn)
        optimizer = CRMQueryOptimizer(db_pool=mock_pool)

        results, total = await optimizer.search_clients_optimized("john")
        assert total == 1
        assert len(results) == 1
        assert "total_count" not in results[0]

    @pytest.mark.asyncio
    async def test_search_clients_no_results(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = _make_pool_with_conn(mock_conn)
        optimizer = CRMQueryOptimizer(db_pool=mock_pool)

        results, total = await optimizer.search_clients_optimized("nonexistent")
        assert total == 0
        assert results == []

    @pytest.mark.asyncio
    async def test_get_practice_statistics(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"status": "active", "priority": "high", "count": 5,
             "total_quoted": 10000, "total_actual": 8000, "total_paid": 6000},
        ])

        mock_pool = _make_pool_with_conn(mock_conn)
        optimizer = CRMQueryOptimizer(db_pool=mock_pool)

        stats = await optimizer.get_practice_statistics()
        assert stats["by_status"]["active"] == 5
        assert stats["financials"]["total_paid"] == 6000.0

    @pytest.mark.asyncio
    async def test_get_practice_statistics_with_filter(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = _make_pool_with_conn(mock_conn)
        optimizer = CRMQueryOptimizer(db_pool=mock_pool)

        stats = await optimizer.get_practice_statistics(assigned_to="user1")
        assert stats["by_status"] == {}

    @pytest.mark.asyncio
    async def test_get_overdue_practices(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"id": 1, "client_name": "John", "status": "active"},
        ])

        mock_pool = _make_pool_with_conn(mock_conn)
        optimizer = CRMQueryOptimizer(db_pool=mock_pool)

        result = await optimizer.get_overdue_practices(days=7)
        assert len(result) == 1


# ── health_check_crm_tables ─────────────────────────────────────────────────


class TestHealthCheckCrmTables:
    @pytest.mark.asyncio
    async def test_returns_checks(self):
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[100, 50, 10, 200, 5, 0])

        mock_pool = _make_pool_with_conn(mock_conn)

        result = await health_check_crm_tables(mock_pool)
        assert result["clients"]["count"] == 100
        assert result["practices"]["count"] == 50
        assert result["orphan_clients"] == 5
        assert result["orphan_practices"] == 0
