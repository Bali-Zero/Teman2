"""
Unit tests for backend/core/redis_manager.py — RedisManager singleton
and TTL configuration.

All Redis connections are mocked to avoid requiring a live Redis server.
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis_manager import TTL_CONFIG, RedisManager, get_ttl

# =============================================================================
# TTL Configuration
# =============================================================================


class TestTTLConfig:
    """Tests for TTL_CONFIG and get_ttl helper."""

    def test_ttl_config_has_default(self) -> None:
        assert "default" in TTL_CONFIG
        assert TTL_CONFIG["default"] == 1800

    def test_get_ttl_exact_prefix_match(self) -> None:
        assert get_ttl("hybrid_search") == 3600
        assert get_ttl("kg:entity") == 21600
        assert get_ttl("kg:traverse") == 21600
        assert get_ttl("query_expand") == 7200
        assert get_ttl("kbli_translate") == 86400
        assert get_ttl("kbli_inspect") == 86400
        assert get_ttl("faq") == 14400
        assert get_ttl("notebooklm") == 14400
        assert get_ttl("session") == 86400

    def test_get_ttl_prefix_with_suffix(self) -> None:
        """Keys that start with a known prefix should get that prefix's TTL."""
        assert get_ttl("hybrid_search:query123") == 3600
        assert get_ttl("kg:entity:some_id") == 21600
        assert get_ttl("session:user:abc") == 86400
        assert get_ttl("faq:visa_questions") == 14400

    def test_get_ttl_unknown_prefix_returns_default(self) -> None:
        assert get_ttl("unknown_key") == 1800
        assert get_ttl("something:random") == 1800
        assert get_ttl("") == 1800

    def test_get_ttl_all_values_are_positive_ints(self) -> None:
        for prefix, ttl in TTL_CONFIG.items():
            assert isinstance(ttl, int), f"TTL for '{prefix}' is not int"
            assert ttl > 0, f"TTL for '{prefix}' is not positive"


# =============================================================================
# RedisManager — Singleton Behavior
# =============================================================================


class TestRedisManagerSingleton:
    """Tests for singleton pattern and reset."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        RedisManager._instance = None

    def teardown_method(self) -> None:
        """Cleanup singleton after each test."""
        RedisManager._instance = None

    def test_get_instance_creates_singleton(self) -> None:
        mgr1 = RedisManager.get_instance()
        mgr2 = RedisManager.get_instance()
        assert mgr1 is mgr2

    def test_reset_clears_singleton(self) -> None:
        mgr1 = RedisManager.get_instance()
        RedisManager.reset()
        mgr2 = RedisManager.get_instance()
        assert mgr1 is not mgr2

    def test_new_instance_defaults(self) -> None:
        mgr = RedisManager()
        assert mgr._async_client is None
        assert mgr._sync_client is None
        assert mgr._available is False
        assert mgr._redis_url is None
        assert mgr._components == {}
        assert mgr._stats["connections_created"] == 0


# =============================================================================
# RedisManager — Initialization
# =============================================================================


class TestRedisManagerInitialize:
    """Tests for RedisManager.initialize()."""

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    def test_initialize_no_url_disables_redis(self) -> None:
        mgr = RedisManager()
        mgr.initialize(redis_url="")
        assert mgr.available is False
        assert mgr._async_client is None
        assert mgr._sync_client is None

    def test_initialize_none_url_reads_settings(self) -> None:
        """When redis_url is None, it reads from settings."""
        mgr = RedisManager()
        with patch("backend.core.redis_manager.RedisManager.initialize"):
            # Just verify it can be called
            mgr.initialize(redis_url=None)

    @patch("redis.from_url")
    @patch("redis.asyncio.from_url")
    def test_initialize_success_both_clients(
        self, mock_async_from_url: MagicMock, mock_sync_from_url: MagicMock,
    ) -> None:
        """Both sync and async clients connect successfully."""
        mock_sync_client = MagicMock()
        mock_sync_client.ping.return_value = True
        mock_sync_from_url.return_value = mock_sync_client

        mock_async_client = MagicMock()
        mock_async_from_url.return_value = mock_async_client

        mgr = RedisManager()
        mgr.initialize(redis_url="redis://localhost:6379/0")

        assert mgr.available is True
        assert mgr._sync_client is mock_sync_client
        assert mgr._async_client is mock_async_client
        assert mgr._stats["connections_created"] == 2

    @patch("redis.from_url")
    @patch("redis.asyncio.from_url")
    def test_initialize_sync_fails_async_works(
        self, mock_async_from_url: MagicMock, mock_sync_from_url: MagicMock,
    ) -> None:
        """Graceful degradation: sync fails but async succeeds."""
        mock_sync_from_url.side_effect = Exception("connection refused")

        mock_async_client = MagicMock()
        mock_async_from_url.return_value = mock_async_client

        mgr = RedisManager()
        mgr.initialize(redis_url="redis://localhost:6379/0")

        assert mgr.available is True  # async still works
        assert mgr._sync_client is None
        assert mgr._async_client is mock_async_client
        assert mgr._stats["connections_created"] == 1

    @patch("redis.from_url")
    @patch("redis.asyncio.from_url")
    def test_initialize_sync_works_async_fails(
        self, mock_async_from_url: MagicMock, mock_sync_from_url: MagicMock,
    ) -> None:
        """Graceful degradation: async fails but sync succeeds."""
        mock_sync_client = MagicMock()
        mock_sync_client.ping.return_value = True
        mock_sync_from_url.return_value = mock_sync_client

        mock_async_from_url.side_effect = Exception("async connection refused")

        mgr = RedisManager()
        mgr.initialize(redis_url="redis://localhost:6379/0")

        assert mgr.available is True  # sync still works
        assert mgr._sync_client is mock_sync_client
        assert mgr._async_client is None
        assert mgr._stats["connections_created"] == 1

    @patch("redis.from_url")
    @patch("redis.asyncio.from_url")
    def test_initialize_both_fail(
        self, mock_async_from_url: MagicMock, mock_sync_from_url: MagicMock,
    ) -> None:
        """Both clients fail — Redis unavailable."""
        mock_sync_from_url.side_effect = Exception("sync fail")
        mock_async_from_url.side_effect = Exception("async fail")

        mgr = RedisManager()
        mgr.initialize(redis_url="redis://localhost:6379/0")

        assert mgr.available is False
        assert mgr._sync_client is None
        assert mgr._async_client is None
        assert mgr._stats["connections_created"] == 0

    @patch("redis.from_url")
    @patch("redis.asyncio.from_url")
    def test_initialize_sync_ping_fails(
        self, mock_async_from_url: MagicMock, mock_sync_from_url: MagicMock,
    ) -> None:
        """Sync client connects but ping fails."""
        mock_sync_client = MagicMock()
        mock_sync_client.ping.side_effect = Exception("ping timeout")
        mock_sync_from_url.return_value = mock_sync_client

        mock_async_client = MagicMock()
        mock_async_from_url.return_value = mock_async_client

        mgr = RedisManager()
        mgr.initialize(redis_url="redis://localhost:6379/0")

        # Sync ping failure means sync client set to None
        assert mgr._sync_client is None
        assert mgr._async_client is mock_async_client
        assert mgr.available is True  # async still available


# =============================================================================
# RedisManager — Client Accessors
# =============================================================================


class TestRedisManagerAccessors:
    """Tests for get_async_client, get_sync_client, register_component."""

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    def test_get_async_client_returns_none_when_unavailable(self) -> None:
        mgr = RedisManager()
        assert mgr.get_async_client() is None

    def test_get_sync_client_returns_none_when_unavailable(self) -> None:
        mgr = RedisManager()
        assert mgr.get_sync_client() is None

    def test_get_async_client_returns_client(self) -> None:
        mgr = RedisManager()
        mock_client = MagicMock()
        mgr._async_client = mock_client
        assert mgr.get_async_client() is mock_client

    def test_get_sync_client_returns_client(self) -> None:
        mgr = RedisManager()
        mock_client = MagicMock()
        mgr._sync_client = mock_client
        assert mgr.get_sync_client() is mock_client

    def test_register_component(self) -> None:
        mgr = RedisManager()
        mgr.register_component("cache_service", "active")
        mgr.register_component("rate_limiter", "fallback")
        assert mgr._components["cache_service"] == "active"
        assert mgr._components["rate_limiter"] == "fallback"

    def test_register_component_overwrites(self) -> None:
        mgr = RedisManager()
        mgr.register_component("cache", "active")
        mgr.register_component("cache", "degraded")
        assert mgr._components["cache"] == "degraded"

    def test_available_property(self) -> None:
        mgr = RedisManager()
        assert mgr.available is False
        mgr._available = True
        assert mgr.available is True


# =============================================================================
# RedisManager — Health Check
# =============================================================================


class TestRedisManagerHealthCheck:
    """Tests for async health_check()."""

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    @pytest.mark.asyncio
    async def test_health_check_unavailable(self) -> None:
        mgr = RedisManager()
        result = await mgr.health_check()
        assert result["connected"] is False
        assert result["latency_ms"] == -1
        assert result["keys"] == 0

    @pytest.mark.asyncio
    async def test_health_check_no_async_client(self) -> None:
        mgr = RedisManager()
        mgr._available = True
        mgr._async_client = None
        result = await mgr.health_check()
        assert result["connected"] is False

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        mgr = RedisManager()
        mgr._available = True

        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.dbsize.return_value = 42
        mock_client.info.return_value = {"used_memory_human": "1.2M"}
        mgr._async_client = mock_client

        result = await mgr.health_check()
        assert result["connected"] is True
        assert result["latency_ms"] >= 0
        assert result["keys"] == 42
        assert result["memory_used"] == "1.2M"

    @pytest.mark.asyncio
    async def test_health_check_ping_fails(self) -> None:
        mgr = RedisManager()
        mgr._available = True

        mock_client = AsyncMock()
        mock_client.ping.side_effect = Exception("connection lost")
        mgr._async_client = mock_client

        result = await mgr.health_check()
        assert result["connected"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_health_check_includes_components(self) -> None:
        mgr = RedisManager()
        mgr.register_component("cache", "active")
        mgr.register_component("rate_limiter", "fallback")

        result = await mgr.health_check()
        assert result["components"]["cache"] == "active"
        assert result["components"]["rate_limiter"] == "fallback"


# =============================================================================
# RedisManager — Stats
# =============================================================================


class TestRedisManagerStats:
    """Tests for get_stats()."""

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    def test_get_stats_default(self) -> None:
        mgr = RedisManager()
        stats = mgr.get_stats()
        assert stats["available"] is False
        assert stats["url_configured"] is False
        assert stats["async_client"] is False
        assert stats["sync_client"] is False
        assert stats["components"] == {}
        assert stats["connections_created"] == 0

    def test_get_stats_after_initialize(self) -> None:
        mgr = RedisManager()
        mgr._available = True
        mgr._redis_url = "redis://localhost:6379/0"
        mgr._async_client = MagicMock()
        mgr._sync_client = MagicMock()
        mgr._stats["connections_created"] = 2
        mgr.register_component("cache", "ok")

        stats = mgr.get_stats()
        assert stats["available"] is True
        assert stats["url_configured"] is True
        assert stats["async_client"] is True
        assert stats["sync_client"] is True
        assert stats["connections_created"] == 2
        assert stats["components"]["cache"] == "ok"


# =============================================================================
# RedisManager — Close
# =============================================================================


class TestRedisManagerClose:
    """Tests for close() and _close_sync()."""

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    def test_close_sync_with_client(self) -> None:
        mgr = RedisManager()
        mock_sync = MagicMock()
        mgr._sync_client = mock_sync
        mgr._close_sync()
        mock_sync.close.assert_called_once()

    def test_close_sync_without_client(self) -> None:
        """Should not raise when no sync client."""
        mgr = RedisManager()
        mgr._close_sync()  # no error

    def test_close_sync_suppresses_exception(self) -> None:
        """close() on sync client that raises should be suppressed."""
        mgr = RedisManager()
        mock_sync = MagicMock()
        mock_sync.close.side_effect = Exception("close failed")
        mgr._sync_client = mock_sync
        mgr._close_sync()  # should not raise

    @pytest.mark.asyncio
    async def test_close_both_clients(self) -> None:
        mgr = RedisManager()
        mock_sync = MagicMock()
        mock_async = AsyncMock()
        mgr._sync_client = mock_sync
        mgr._async_client = mock_async

        await mgr.close()

        mock_sync.close.assert_called_once()
        mock_async.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_clients(self) -> None:
        """Should not raise when no clients exist."""
        mgr = RedisManager()
        await mgr.close()  # no error

    @pytest.mark.asyncio
    async def test_close_async_suppresses_exception(self) -> None:
        mgr = RedisManager()
        mock_async = AsyncMock()
        mock_async.close.side_effect = Exception("async close failed")
        mgr._async_client = mock_async

        await mgr.close()  # should not raise

    def test_reset_calls_close_sync(self) -> None:
        mgr = RedisManager.get_instance()
        mock_sync = MagicMock()
        mgr._sync_client = mock_sync

        RedisManager.reset()

        mock_sync.close.assert_called_once()
        assert RedisManager._instance is None


# =============================================================================
# RedisManager — Reconnect Loop (Bug Regression Tests)
# =============================================================================


class TestRedisManagerReconnectLoop:
    """
    Regression tests for reconnect loop bugs.

    Bug fixes covered:
    1. _reconnect_loop must restore BOTH async AND sync clients so rate-limiter
       becomes fully operational after reconnect (not just async cache).
    2. _start_reconnect_loop called from sync context must set _reconnect_pending=True
       so _ensure_reconnect_loop() starts it on the first async call.
    """

    def setup_method(self) -> None:
        RedisManager._instance = None

    def teardown_method(self) -> None:
        RedisManager._instance = None

    def test_start_reconnect_loop_sets_pending_when_no_event_loop(self) -> None:
        """
        BUG: When _start_reconnect_loop() is called outside an event loop
        (e.g., sync test setup or CLI), it silently dropped the reconnect
        intent. The reconnect loop never started.

        FIX: Sets _reconnect_pending=True so async callers can start it later.
        """
        mgr = RedisManager()
        mgr._redis_url = "redis://localhost:6379"
        # There is no running event loop in this sync test
        mgr._start_reconnect_loop()
        assert getattr(mgr, "_reconnect_pending", False) is True
        assert mgr._reconnect_task is None

    @pytest.mark.asyncio
    async def test_ensure_reconnect_loop_starts_deferred_task(self) -> None:
        """
        _ensure_reconnect_loop() must start the task when _reconnect_pending=True.
        """
        mgr = RedisManager()
        mgr._redis_url = "redis://localhost:6379"
        mgr._available = False
        mgr._reconnect_pending = True

        mgr._ensure_reconnect_loop()

        assert mgr._reconnect_task is not None
        assert not mgr._reconnect_task.done()
        assert mgr._reconnect_pending is False

        # Clean up
        mgr._reconnect_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await mgr._reconnect_task

    @pytest.mark.asyncio
    async def test_ensure_reconnect_loop_noop_when_available(self) -> None:
        """
        If Redis became available before the deferred loop fires, do nothing.
        """
        mgr = RedisManager()
        mgr._redis_url = "redis://localhost:6379"
        mgr._available = True
        mgr._reconnect_pending = True

        mgr._ensure_reconnect_loop()

        # Should clear the flag but not create a task
        assert mgr._reconnect_pending is False
        assert mgr._reconnect_task is None

    @pytest.mark.asyncio
    async def test_ensure_reconnect_loop_noop_when_not_pending(self) -> None:
        """When _reconnect_pending is False, _ensure_reconnect_loop is a no-op."""
        mgr = RedisManager()
        mgr._reconnect_pending = False

        mgr._ensure_reconnect_loop()

        assert mgr._reconnect_task is None

    @pytest.mark.asyncio
    async def test_health_check_starts_deferred_reconnect(self) -> None:
        """
        health_check() must call _ensure_reconnect_loop() so the deferred
        task starts on the first async call into the manager.
        """
        mgr = RedisManager()
        mgr._redis_url = "redis://localhost:6379"
        mgr._available = False
        mgr._reconnect_pending = True

        # health_check should start the loop even though Redis is unavailable
        await mgr.health_check()

        assert mgr._reconnect_task is not None
        assert mgr._reconnect_pending is False

        # Clean up
        mgr._reconnect_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await mgr._reconnect_task

    @pytest.mark.asyncio
    async def test_reconnect_loop_restores_both_clients(self) -> None:
        """
        BUG: _reconnect_loop only restored _async_client. _sync_client stayed
        None so the rate-limiter middleware remained in in-memory fallback mode
        even after Redis came back.

        FIX: _reconnect_loop must restore both async and sync clients.
        """
        mgr = RedisManager()
        mgr._redis_url = "redis://localhost:6379"
        mgr._available = False

        mock_async_client = AsyncMock()
        mock_async_client.ping.return_value = True

        mock_sync_client = MagicMock()
        mock_sync_client.ping.return_value = True

        with (
            patch("redis.asyncio.from_url", return_value=mock_async_client),
            patch("redis.from_url", return_value=mock_sync_client),
        ):
            # Patch sleep to avoid waiting 30 seconds
            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Run one iteration of the loop; it should reconnect and return
                await mgr._reconnect_loop()

        assert mgr._available is True
        assert mgr._async_client is mock_async_client, "async client must be restored"
        assert mgr._sync_client is mock_sync_client, "sync client must be restored (rate-limiter)"

    @pytest.mark.asyncio
    async def test_reconnect_loop_async_only_when_sync_fails(self) -> None:
        """
        If sync client cannot reconnect, async-only mode is used and
        _available is still set to True (graceful degradation).
        """
        mgr = RedisManager()
        mgr._redis_url = "redis://localhost:6379"
        mgr._available = False

        mock_async_client = AsyncMock()
        mock_async_client.ping.return_value = True

        with (
            patch("redis.asyncio.from_url", return_value=mock_async_client),
            patch("redis.from_url", side_effect=Exception("sync refused")),
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await mgr._reconnect_loop()

        assert mgr._available is True
        assert mgr._async_client is mock_async_client
        assert mgr._sync_client is None  # Sync failed but async-only is fine

    @pytest.mark.asyncio
    async def test_reconnect_loop_cancelled_during_sleep(self) -> None:
        """
        When close() cancels the task during asyncio.sleep(), CancelledError
        must propagate cleanly without being swallowed.
        """
        mgr = RedisManager()
        mgr._redis_url = "redis://localhost:6379"
        mgr._available = False

        async def cancel_immediately(*args: object, **kwargs: object) -> None:
            raise asyncio.CancelledError()

        with patch("asyncio.sleep", side_effect=cancel_immediately):
            with pytest.raises(asyncio.CancelledError):
                await mgr._reconnect_loop()
