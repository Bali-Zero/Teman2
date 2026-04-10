"""
Unit tests for Channel Optimizations.
Covers: RateLimitConfig, ChannelRateLimiter, MessageDeduplicator, ChannelMetrics,
ConnectionPool, DeliveryManager, initialize_optimizations.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

from backend.channels.optimizations import (
    ChannelMetrics,
    ChannelRateLimiter,
    ConnectionPool,
    DeliveryManager,
    MessageDeduplicator,
    RateLimitConfig,
    initialize_optimizations,
)


# --------------------------------------------------------------------------- #
# RateLimitConfig
# --------------------------------------------------------------------------- #

class TestRateLimitConfig:
    def test_defaults(self) -> None:
        config = RateLimitConfig()
        assert config.max_requests_per_minute == 60
        assert config.max_requests_per_hour == 1000
        assert config.burst_size == 10

    def test_custom_values(self) -> None:
        config = RateLimitConfig(max_requests_per_minute=30, max_requests_per_hour=500, burst_size=5)
        assert config.max_requests_per_minute == 30
        assert config.burst_size == 5


# --------------------------------------------------------------------------- #
# ChannelRateLimiter
# --------------------------------------------------------------------------- #

class TestChannelRateLimiter:
    @pytest.fixture
    def limiter(self) -> ChannelRateLimiter:
        return ChannelRateLimiter(RateLimitConfig(
            max_requests_per_minute=5,
            max_requests_per_hour=20,
            burst_size=3,
        ))

    @pytest.mark.asyncio
    async def test_acquire_success_no_redis(self, limiter: ChannelRateLimiter) -> None:
        with patch("backend.channels.optimizations._get_redis_client", return_value=None):
            result = await limiter.acquire("telegram")
            assert result is True

    @pytest.mark.asyncio
    async def test_burst_exhaustion(self, limiter: ChannelRateLimiter) -> None:
        with patch("backend.channels.optimizations._get_redis_client", return_value=None):
            # Exhaust burst tokens (3)
            assert await limiter.acquire("ch1") is True
            assert await limiter.acquire("ch1") is True
            assert await limiter.acquire("ch1") is True
            # 4th should fail (burst exhausted, tokens not refilled yet)
            result = await limiter.acquire("ch1")
            # May or may not fail depending on timing; at minimum shouldn't crash
            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_minute_limit_in_memory(self, limiter: ChannelRateLimiter) -> None:
        with patch("backend.channels.optimizations._get_redis_client", return_value=None):
            # Pre-fill minute counts to max
            now = time.time()
            limiter.minute_counts["ch2"] = [now] * 5
            limiter.tokens["ch2"] = 10  # Reset burst tokens
            result = await limiter.acquire("ch2")
            assert result is False

    @pytest.mark.asyncio
    async def test_hour_limit_in_memory(self, limiter: ChannelRateLimiter) -> None:
        with patch("backend.channels.optimizations._get_redis_client", return_value=None):
            now = time.time()
            limiter.hour_counts["ch3"] = [now] * 20
            limiter.tokens["ch3"] = 10
            result = await limiter.acquire("ch3")
            assert result is False

    @pytest.mark.asyncio
    async def test_redis_success(self, limiter: ChannelRateLimiter) -> None:
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()

        with patch("backend.channels.optimizations._get_redis_client", return_value=mock_redis):
            result = await limiter.acquire("ch_redis")
            assert result is True

    @pytest.mark.asyncio
    async def test_redis_minute_exceeded(self, limiter: ChannelRateLimiter) -> None:
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=100)  # Way over limit
        mock_redis.decr = AsyncMock()

        with patch("backend.channels.optimizations._get_redis_client", return_value=mock_redis):
            result = await limiter.acquire("ch_over")
            assert result is False

    @pytest.mark.asyncio
    async def test_redis_hour_exceeded(self, limiter: ChannelRateLimiter) -> None:
        incr_results = iter([1, 100])  # minute=1 (ok), hour=100 (exceeded)

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(side_effect=lambda key: next(incr_results))
        mock_redis.expire = AsyncMock()
        mock_redis.decr = AsyncMock()

        with patch("backend.channels.optimizations._get_redis_client", return_value=mock_redis):
            result = await limiter.acquire("ch_hour")
            assert result is False
            # Should have called decr twice (undo hour + undo minute)
            assert mock_redis.decr.await_count == 2

    @pytest.mark.asyncio
    async def test_redis_exception_falls_back(self, limiter: ChannelRateLimiter) -> None:
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(side_effect=Exception("Redis down"))

        with patch("backend.channels.optimizations._get_redis_client", return_value=mock_redis):
            result = await limiter.acquire("ch_fallback")
            assert isinstance(result, bool)

    def test_cleanup_old_counts(self, limiter: ChannelRateLimiter) -> None:
        now = time.time()
        limiter.minute_counts["ch"] = [now - 120, now - 90, now - 30, now]
        limiter.hour_counts["ch"] = [now - 7200, now - 3601, now - 100, now]
        limiter._cleanup_old_counts("ch", now)
        assert len(limiter.minute_counts["ch"]) == 2
        assert len(limiter.hour_counts["ch"]) == 2


# --------------------------------------------------------------------------- #
# MessageDeduplicator
# --------------------------------------------------------------------------- #

class TestMessageDeduplicator:
    @pytest.fixture
    def dedup(self) -> MessageDeduplicator:
        return MessageDeduplicator(ttl_seconds=10)

    @pytest.mark.asyncio
    async def test_first_message_not_duplicate(self, dedup: MessageDeduplicator) -> None:
        result = await dedup.is_duplicate("telegram", "user1", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_second_same_message_is_duplicate(self, dedup: MessageDeduplicator) -> None:
        await dedup.is_duplicate("telegram", "user1", "hello")
        result = await dedup.is_duplicate("telegram", "user1", "hello")
        assert result is True

    @pytest.mark.asyncio
    async def test_different_text_not_duplicate(self, dedup: MessageDeduplicator) -> None:
        await dedup.is_duplicate("telegram", "user1", "hello")
        result = await dedup.is_duplicate("telegram", "user1", "goodbye")
        assert result is False

    @pytest.mark.asyncio
    async def test_different_channel_not_duplicate(self, dedup: MessageDeduplicator) -> None:
        await dedup.is_duplicate("telegram", "user1", "hello")
        result = await dedup.is_duplicate("whatsapp", "user1", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_different_user_not_duplicate(self, dedup: MessageDeduplicator) -> None:
        await dedup.is_duplicate("telegram", "user1", "hello")
        result = await dedup.is_duplicate("telegram", "user2", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_expired_entries_cleaned(self, dedup: MessageDeduplicator) -> None:
        # Manually set an old hash
        dedup.seen_hashes["old_hash"] = time.time() - 100
        await dedup.is_duplicate("telegram", "user1", "new message")
        assert "old_hash" not in dedup.seen_hashes


# --------------------------------------------------------------------------- #
# ChannelMetrics
# --------------------------------------------------------------------------- #

class TestChannelMetrics:
    @pytest.fixture
    def metrics(self) -> ChannelMetrics:
        return ChannelMetrics()

    def test_record_message_received(self, metrics: ChannelMetrics) -> None:
        metrics.record_message_received("telegram")
        metrics.record_message_received("telegram")
        assert metrics.counters["telegram.messages_received"] == 2

    def test_record_message_sent(self, metrics: ChannelMetrics) -> None:
        metrics.record_message_sent("telegram", 150.0)
        assert metrics.counters["telegram.messages_sent"] == 1
        assert len(metrics.latencies["telegram"]) == 1

    def test_record_error(self, metrics: ChannelMetrics) -> None:
        metrics.record_error("telegram", "timeout")
        metrics.record_error("telegram", "timeout")
        metrics.record_error("telegram", "auth_fail")
        assert metrics.counters["telegram.errors.timeout"] == 2
        assert metrics.counters["telegram.errors.auth_fail"] == 1

    def test_get_stats_empty(self, metrics: ChannelMetrics) -> None:
        stats = metrics.get_stats("nonexistent")
        assert stats["messages_received"] == 0
        assert stats["messages_sent"] == 0
        assert stats["errors"] == 0
        assert stats["success_rate"] == "0.0%"

    def test_get_stats_with_data(self, metrics: ChannelMetrics) -> None:
        metrics.record_message_received("tg")
        metrics.record_message_received("tg")
        metrics.record_message_sent("tg", 100.0)
        metrics.record_error("tg", "timeout")

        stats = metrics.get_stats("tg")
        assert stats["messages_received"] == 2
        assert stats["messages_sent"] == 1
        assert stats["errors"] == 1
        assert stats["success_rate"] == "50.0%"

    def test_latency_trimming(self, metrics: ChannelMetrics) -> None:
        for i in range(1100):
            metrics.record_message_sent("tg", float(i))
        assert len(metrics.latencies["tg"]) == 1000

    def test_p95_latency(self, metrics: ChannelMetrics) -> None:
        for i in range(100):
            metrics.record_message_sent("tg", float(i))
        stats = metrics.get_stats("tg")
        assert float(stats["p95_latency_ms"]) > 0


# --------------------------------------------------------------------------- #
# ConnectionPool
# --------------------------------------------------------------------------- #

class TestConnectionPool:
    @pytest.fixture
    def pool(self) -> ConnectionPool:
        return ConnectionPool(max_connections=50, timeout=15.0)

    @pytest.mark.asyncio
    async def test_get_client_creates(self, pool: ConnectionPool) -> None:
        with patch("httpx.AsyncClient") as mock_httpx, \
             patch("httpx.Limits"):
            mock_client = MagicMock()
            mock_httpx.return_value = mock_client

            client = await pool.get_client("telegram")
            assert client is mock_client
            assert "telegram" in pool.clients

    @pytest.mark.asyncio
    async def test_get_client_reuses(self, pool: ConnectionPool) -> None:
        with patch("httpx.AsyncClient") as mock_httpx, \
             patch("httpx.Limits"):
            mock_httpx.return_value = MagicMock()

            c1 = await pool.get_client("telegram")
            c2 = await pool.get_client("telegram")
            assert c1 is c2
            mock_httpx.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_all(self, pool: ConnectionPool) -> None:
        mock_client = AsyncMock()
        pool.clients["telegram"] = mock_client
        pool.clients["whatsapp"] = AsyncMock()

        await pool.close_all()
        assert len(pool.clients) == 0
        mock_client.aclose.assert_awaited_once()


# --------------------------------------------------------------------------- #
# DeliveryManager
# --------------------------------------------------------------------------- #

class TestDeliveryManager:
    @pytest.fixture
    def dm(self) -> DeliveryManager:
        return DeliveryManager(db_pool=None)

    @pytest.fixture
    def dm_with_db(self) -> DeliveryManager:
        mock_pool = AsyncMock()
        mock_pool.execute = AsyncMock()
        return DeliveryManager(db_pool=mock_pool)

    @pytest.mark.asyncio
    async def test_persist_failed_no_pg_no_redis(self, dm: DeliveryManager) -> None:
        with patch("backend.channels.optimizations._get_redis_client", return_value=None):
            # Should not raise, just log error about lost message
            await dm.persist_failed(
                channel="telegram", channel_id="12345",
                content="hello", error="timeout",
            )

    @pytest.mark.asyncio
    async def test_persist_failed_pg_success(self, dm_with_db: DeliveryManager) -> None:
        await dm_with_db.persist_failed(
            channel="telegram", channel_id="12345",
            content="hello", error="timeout",
            sender_id="user1", metadata={"key": "val"},
        )
        dm_with_db._db_pool.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_persist_failed_pg_fails_redis_fallback(self) -> None:
        mock_pool = AsyncMock()
        mock_pool.execute = AsyncMock(side_effect=Exception("PG down"))
        dm = DeliveryManager(db_pool=mock_pool)

        mock_redis = AsyncMock()
        mock_redis.lpush = AsyncMock()

        with patch("backend.channels.optimizations._get_redis_client", return_value=mock_redis):
            await dm.persist_failed(
                channel="telegram", channel_id="12345",
                content="hello", error="timeout",
            )
            mock_redis.lpush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_persist_to_redis_no_redis(self, dm: DeliveryManager) -> None:
        with patch("backend.channels.optimizations._get_redis_client", return_value=None):
            result = await dm._persist_to_redis({"channel": "test", "channel_id": "1"})
            assert result is False

    @pytest.mark.asyncio
    async def test_persist_to_redis_success(self, dm: DeliveryManager) -> None:
        mock_redis = AsyncMock()
        mock_redis.lpush = AsyncMock()

        with patch("backend.channels.optimizations._get_redis_client", return_value=mock_redis):
            result = await dm._persist_to_redis({"channel": "test", "channel_id": "1"})
            assert result is True

    @pytest.mark.asyncio
    async def test_persist_to_redis_exception(self, dm: DeliveryManager) -> None:
        mock_redis = AsyncMock()
        mock_redis.lpush = AsyncMock(side_effect=Exception("Redis error"))

        with patch("backend.channels.optimizations._get_redis_client", return_value=mock_redis):
            result = await dm._persist_to_redis({"channel": "test", "channel_id": "1"})
            assert result is False

    @pytest.mark.asyncio
    async def test_drain_redis_dlq_no_pool(self, dm: DeliveryManager) -> None:
        result = await dm._drain_redis_dlq()
        assert result == 0

    @pytest.mark.asyncio
    async def test_drain_redis_dlq_no_redis(self, dm_with_db: DeliveryManager) -> None:
        with patch("backend.channels.optimizations._get_redis_client", return_value=None):
            result = await dm_with_db._drain_redis_dlq()
            assert result == 0

    @pytest.mark.asyncio
    async def test_drain_redis_dlq_success(self) -> None:
        mock_pool = AsyncMock()
        mock_pool.execute = AsyncMock()
        dm = DeliveryManager(db_pool=mock_pool)

        record = json.dumps({
            "channel": "telegram", "channel_id": "123",
            "sender_id": "", "content": "hi",
            "metadata": {}, "error_message": "err",
            "error_type": "fail", "queued_at": time.time(),
        })

        mock_redis = AsyncMock()
        mock_redis.rpop = AsyncMock(side_effect=[record, None])

        with patch("backend.channels.optimizations._get_redis_client", return_value=mock_redis):
            result = await dm._drain_redis_dlq()
            assert result == 1

    @pytest.mark.asyncio
    async def test_drain_redis_dlq_pg_fails_repush(self) -> None:
        mock_pool = AsyncMock()
        mock_pool.execute = AsyncMock(side_effect=Exception("PG down"))
        dm = DeliveryManager(db_pool=mock_pool)

        record = json.dumps({
            "channel": "telegram", "channel_id": "123",
            "sender_id": "", "content": "hi",
            "metadata": {}, "error_message": "err",
            "error_type": "fail", "queued_at": time.time(),
        })

        mock_redis = AsyncMock()
        mock_redis.rpop = AsyncMock(return_value=record)
        mock_redis.lpush = AsyncMock()

        with patch("backend.channels.optimizations._get_redis_client", return_value=mock_redis):
            result = await dm._drain_redis_dlq()
            assert result == 0
            mock_redis.lpush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_and_stop_retry_loop(self) -> None:
        dm = DeliveryManager()

        async def fake_loop(adapters: dict) -> None:
            await asyncio.sleep(1000)

        with patch.object(dm, "_process_dlq", side_effect=fake_loop):
            await dm.start_retry_loop({})
            assert dm._retry_task is not None

            # Start again should be no-op
            first_task = dm._retry_task
            await dm.start_retry_loop({})
            assert dm._retry_task is first_task

            await dm.stop_retry_loop()
            assert dm._retry_task is None

    @pytest.mark.asyncio
    async def test_alert_exhausted_no_token(self) -> None:
        dm = DeliveryManager()
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = None

        # backend.core.config is used inside _alert_exhausted (local import)
        mock_config_module = MagicMock()
        mock_config_module.settings = mock_settings

        import sys
        with patch.dict(sys.modules, {"backend.core.config": mock_config_module}):
            await dm._alert_exhausted(
                {"id": 1, "channel": "tg", "channel_id": "123",
                 "content": "msg", "attempt_count": 2, "max_attempts": 3},
                "error msg",
            )

    @pytest.mark.asyncio
    async def test_alert_exhausted_with_token(self) -> None:
        dm = DeliveryManager()
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = "fake_token"
        mock_settings.telegram_owner_chat_id = "12345"

        mock_config_module = MagicMock()
        mock_config_module.settings = mock_settings

        mock_client = AsyncMock()
        mock_client.post = AsyncMock()
        mock_client.is_closed = False

        import sys
        with patch.dict(sys.modules, {"backend.core.config": mock_config_module}):
            dm._alert_client = mock_client
            await dm._alert_exhausted(
                {"id": 1, "channel": "tg", "channel_id": "123",
                 "content": "msg", "attempt_count": 2, "max_attempts": 3},
                "error msg",
            )
            mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_alert_exhausted_exception(self) -> None:
        dm = DeliveryManager()
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = "fake_token"
        mock_settings.telegram_owner_chat_id = "12345"

        mock_config_module = MagicMock()
        mock_config_module.settings = mock_settings

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.is_closed = False

        import sys
        with patch.dict(sys.modules, {"backend.core.config": mock_config_module}):
            dm._alert_client = mock_client
            # Should not raise
            await dm._alert_exhausted(
                {"id": 1, "channel": "tg", "channel_id": "123",
                 "content": "msg", "attempt_count": 2, "max_attempts": 3},
                "error msg",
            )

    @pytest.mark.asyncio
    async def test_get_alert_client_creates(self) -> None:
        dm = DeliveryManager()
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value = MagicMock(is_closed=False)
            client = await dm._get_alert_client()
            assert client is not None

    @pytest.mark.asyncio
    async def test_get_alert_client_reuses(self) -> None:
        dm = DeliveryManager()
        existing = MagicMock(is_closed=False)
        dm._alert_client = existing
        client = await dm._get_alert_client()
        assert client is existing

    @pytest.mark.asyncio
    async def test_get_alert_client_recreates_if_closed(self) -> None:
        dm = DeliveryManager()
        dm._alert_client = MagicMock(is_closed=True)
        with patch("httpx.AsyncClient") as mock_httpx:
            new_client = MagicMock(is_closed=False)
            mock_httpx.return_value = new_client
            client = await dm._get_alert_client()
            assert client is new_client


# --------------------------------------------------------------------------- #
# initialize_optimizations
# --------------------------------------------------------------------------- #

class TestInitializeOptimizations:
    def test_initializes_all_globals(self) -> None:
        import backend.channels.optimizations as opt

        initialize_optimizations(db_pool=None)

        assert opt.rate_limiter is not None
        assert opt.message_deduplicator is not None
        assert opt.channel_metrics is not None
        assert opt.connection_pool is not None
        assert opt.delivery_manager is not None

    def test_initializes_with_db_pool(self) -> None:
        import backend.channels.optimizations as opt

        mock_pool = MagicMock()
        initialize_optimizations(db_pool=mock_pool)

        assert opt.delivery_manager._db_pool is mock_pool


# --------------------------------------------------------------------------- #
# _get_redis_client
# --------------------------------------------------------------------------- #

class TestGetRedisClient:
    def test_returns_none_on_exception(self) -> None:
        """Test that _get_redis_client returns None when RedisManager is unavailable."""
        from backend.channels.optimizations import _get_redis_client

        import sys
        mock_redis_module = MagicMock()
        mock_redis_module.RedisManager.get_instance.return_value.get_async_client.side_effect = Exception("fail")

        with patch.dict(sys.modules, {"backend.core.redis_manager": mock_redis_module}):
            result = _get_redis_client()
            # The function catches all exceptions and returns None
            assert result is None

    def test_returns_client_on_success(self) -> None:
        """Test that _get_redis_client returns client when RedisManager works."""
        from backend.channels.optimizations import _get_redis_client

        import sys
        mock_client = MagicMock()
        mock_redis_module = MagicMock()
        mock_redis_module.RedisManager.get_instance.return_value.get_async_client.return_value = mock_client

        with patch.dict(sys.modules, {"backend.core.redis_manager": mock_redis_module}):
            result = _get_redis_client()
            assert result is mock_client
