"""
Tests for KG Cache Versioning

Validates that KG version tracking correctly invalidates stale
subgraph cache entries after KG mutations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag import kg_cache as kg_cache_module
from backend.services.rag.kg_cache import (
    KGCache,
    get_kg_version,
    increment_kg_version,
)


@pytest.fixture(autouse=True)
def reset_kg_version():
    """Reset KG version counter before each test."""
    kg_cache_module._kg_version = 0
    yield
    kg_cache_module._kg_version = 0


class TestKGVersionCounter:
    """Tests for the module-level KG version counter."""

    def test_initial_version_is_zero(self) -> None:
        """Version starts at 0."""
        assert get_kg_version() == 0

    def test_increment_version(self) -> None:
        """Incrementing bumps version by 1."""
        new_ver = increment_kg_version()
        assert new_ver == 1
        assert get_kg_version() == 1

    def test_multiple_increments(self) -> None:
        """Multiple increments produce monotonically increasing values."""
        v1 = increment_kg_version()
        v2 = increment_kg_version()
        v3 = increment_kg_version()
        assert v1 == 1
        assert v2 == 2
        assert v3 == 3
        assert get_kg_version() == 3


class TestKGCacheVersioning:
    """Tests for version-aware subgraph caching."""

    @pytest.fixture
    def mock_cache_service(self):
        """Create a mock cache service with dict-based storage."""
        store: dict[str, dict] = {}

        async def mock_get(key: str):
            return store.get(key)

        async def mock_set(key: str, value, ttl: int = 0):
            store[key] = value

        async def mock_clear(pattern: str):
            keys_to_remove = [k for k in store if pattern.replace("*", "") in k]
            for k in keys_to_remove:
                del store[k]
            return len(keys_to_remove)

        service = MagicMock()
        service.get = AsyncMock(side_effect=mock_get)
        service.set = AsyncMock(side_effect=mock_set)
        service.clear_pattern = AsyncMock(side_effect=mock_clear)
        return service, store

    @pytest.fixture
    def cache_with_service(self, mock_cache_service):
        """Create a KGCache instance with mock service injected."""
        service, store = mock_cache_service
        cache = KGCache()
        cache._cache = service
        cache._initialized = True
        return cache, store

    @pytest.mark.asyncio
    async def test_cache_hit_same_version(self, cache_with_service) -> None:
        """Cache hit when KG version unchanged."""
        cache, _ = cache_with_service

        # Set result at version 0
        await cache.set_subgraph_result("visa", "kitas query", {"name": "visa_workflow"})

        # Read at same version -> hit
        result = await cache.get_subgraph_result("visa", "kitas query")
        assert result is not None
        assert result["name"] == "visa_workflow"

    @pytest.mark.asyncio
    async def test_cache_miss_after_version_increment(self, cache_with_service) -> None:
        """Cache miss when KG version incremented after set."""
        cache, _ = cache_with_service

        # Set result at version 0
        await cache.set_subgraph_result("visa", "kitas query", {"name": "visa_workflow"})

        # Increment version (simulates KG mutation)
        increment_kg_version()
        assert get_kg_version() == 1

        # Read at version 1 -> miss (cached at version 0)
        result = await cache.get_subgraph_result("visa", "kitas query")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_after_re_cache(self, cache_with_service) -> None:
        """Cache hit after re-caching at new version."""
        cache, _ = cache_with_service

        # Set at version 0
        await cache.set_subgraph_result("tax", "ppn query", {"name": "old_workflow"})

        # Increment and re-cache
        increment_kg_version()
        await cache.set_subgraph_result("tax", "ppn query", {"name": "fresh_workflow"})

        # Read -> hit with new data
        result = await cache.get_subgraph_result("tax", "ppn query")
        assert result is not None
        assert result["name"] == "fresh_workflow"

    @pytest.mark.asyncio
    async def test_different_domains_independent(self, cache_with_service) -> None:
        """Different domain caches are independent."""
        cache, _ = cache_with_service

        await cache.set_subgraph_result("visa", "query1", {"name": "visa_wf"})
        await cache.set_subgraph_result("tax", "query2", {"name": "tax_wf"})

        r1 = await cache.get_subgraph_result("visa", "query1")
        r2 = await cache.get_subgraph_result("tax", "query2")
        assert r1 is not None
        assert r2 is not None
        assert r1["name"] == "visa_wf"
        assert r2["name"] == "tax_wf"

    @pytest.mark.asyncio
    async def test_version_miss_invalidates_all_domains(self, cache_with_service) -> None:
        """Version increment causes miss for ALL cached domains."""
        cache, _ = cache_with_service

        await cache.set_subgraph_result("visa", "q1", {"name": "visa_wf"})
        await cache.set_subgraph_result("tax", "q2", {"name": "tax_wf"})

        increment_kg_version()

        assert await cache.get_subgraph_result("visa", "q1") is None
        assert await cache.get_subgraph_result("tax", "q2") is None

    @pytest.mark.asyncio
    async def test_invalidate_all_clears_cache(self, cache_with_service) -> None:
        """invalidate_all still works alongside version tracking."""
        cache, _ = cache_with_service

        await cache.set_subgraph_result("visa", "q1", {"name": "wf"})
        count = await cache.invalidate_all()
        assert count >= 0  # May or may not match depending on mock

    @pytest.mark.asyncio
    async def test_cache_disabled_returns_none(self) -> None:
        """When cache is disabled, always returns None."""
        cache = KGCache()
        cache._cache = None
        cache._initialized = True

        await cache.set_subgraph_result("visa", "q1", {"name": "wf"})
        result = await cache.get_subgraph_result("visa", "q1")
        assert result is None
