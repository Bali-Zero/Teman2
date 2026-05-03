"""Redis connectivity test — verifies SemanticCache can reach Redis."""

import pytest

from nuzantara_graph.config import Settings
from nuzantara_graph.services.cache import SemanticCache
from tests.connectivity.conftest import LOCAL_REDIS_URL, REDIS_AVAILABLE


@pytest.fixture(scope="module")
def redis_settings():
    return Settings(redis_url=LOCAL_REDIS_URL)


@pytest.mark.skipif(
    not REDIS_AVAILABLE,
    reason="Redis not reachable at redis://localhost:6379/0 or redis://localhost:6380/0",
)
class TestRedisConnectivity:

    @pytest.mark.asyncio
    async def test_health_check(self, redis_settings):
        cache = SemanticCache.from_settings(redis_settings)
        try:
            result = await cache.health_check()
            assert result["ok"] is True
            assert result["status"] == "healthy"
            assert result["ping"] is True
        finally:
            await cache.close()

    @pytest.mark.asyncio
    async def test_set_and_get(self, redis_settings):
        cache = SemanticCache.from_settings(redis_settings)
        try:
            test_query = "__connectivity_test_query__"
            test_data = {"answer": "test", "ok": True}

            await cache.set(test_query, test_data, ttl=10)
            result = await cache.get(test_query)

            assert result is not None
            assert result["answer"] == "test"
            assert result["ok"] is True

            # Clean up
            await cache.invalidate(test_query)
            assert await cache.get(test_query) is None
        finally:
            await cache.close()

    @pytest.mark.asyncio
    async def test_pubsub(self, redis_settings):
        cache = SemanticCache.from_settings(redis_settings)
        try:
            await cache.publish_node_event(
                run_id="test-run-123",
                event={"node": "test", "status": "ok"},
            )
        finally:
            await cache.close()
