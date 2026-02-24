"""Redis connectivity test — verifies SemanticCache can reach Redis."""

import socket

import pytest

from nuzantara_graph.config import Settings
from nuzantara_graph.services.cache import SemanticCache


def _redis_available() -> tuple[bool, int]:
    """Check if Redis is available on port 6379 or 6380."""
    for port in (6379, 6380):
        try:
            s = socket.create_connection(("localhost", port), timeout=1)
            s.close()
            return True, port
        except (OSError, ConnectionRefusedError):
            continue
    return False, 0


_available, _redis_port = _redis_available()


@pytest.fixture(scope="module")
def redis_settings():
    return Settings(redis_url=f"redis://localhost:{_redis_port}/0")


@pytest.mark.skipif(not _available, reason="Redis not running on :6379 or :6380")
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
