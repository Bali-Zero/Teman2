"""
Unit tests for the new rate-limiter hardening:
- Redis error flips to fallback mode and records metrics.
- Fallback mode periodically retries reconnecting.
- get_rate_limit_stats() surfaces metrics + last_error.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from backend.middleware.rate_limiter import (
    RateLimiter,
    _rate_limit_storage,
    get_rate_limit_stats,
)


def _fresh_limiter(redis_client=None):
    """
    Build a RateLimiter with a stubbed RedisManager. RedisManager is
    imported lazily inside _connect_from_manager() via
    `from backend.core.redis_manager import RedisManager`, so we patch
    the source module.
    """
    with patch("backend.core.redis_manager.RedisManager") as RM:
        mgr = MagicMock()
        mgr.get_sync_client.return_value = redis_client
        mgr.register_component = MagicMock()
        RM.get_instance.return_value = mgr
        return RateLimiter()


class TestRedisErrorBehavior:
    def test_redis_exception_records_metrics_and_last_error(self):
        """
        A runtime Redis error MUST record the error in metrics and fall
        back to the half-limit in-memory path for this request. We do
        NOT permanently flip redis_available — the original per-request
        fail-safe semantics (retry Redis every call) are preserved.
        """
        client = MagicMock()
        pipe = MagicMock()
        pipe.execute.side_effect = ConnectionError("redis down")
        client.pipeline.return_value = pipe

        rl = _fresh_limiter(redis_client=client)
        assert rl.redis_available is True

        _, info = rl.is_allowed("k1", limit=10, window=60)
        # Fell back to memory with HALF limit
        assert info["limit"] == 5  # max(1, 10//2)
        assert info["backend"] == "memory_degraded"
        assert rl.metrics["redis_errors"] == 1
        assert rl._last_error is not None
        assert "ConnectionError" in rl._last_error
        # Per-call fail-safe: redis_available stays True so the NEXT call
        # tries Redis again.
        assert rl.redis_available is True

    def test_memory_backend_increments_metric(self):
        """When Redis was unavailable at boot, memory path increments counter."""
        rl = _fresh_limiter(redis_client=None)  # no Redis available
        assert rl.redis_available is False
        _, info = rl.is_allowed("k-mem", limit=20, window=60)
        assert info["backend"] == "memory"
        assert rl.metrics["memory_fallback_requests"] >= 1


class TestBootRecovery:
    """
    Recovery applies to the "Redis was down at boot, comes back later"
    scenario — NOT runtime errors (those use per-call fail-safe).
    """

    def test_try_recover_reconnects_on_cooldown(self):
        rl = _fresh_limiter(redis_client=None)  # boot with no Redis
        assert rl.redis_available is False

        # Forge a healthy client that will be returned on the next
        # _connect_from_manager() call.
        healthy = MagicMock()
        healthy.pipeline.return_value.execute.return_value = [0, 0, 1, True]

        # Force last_recovery_attempt far enough in the past to allow retry.
        rl._last_recovery_attempt = time.time() - (rl._RECOVERY_COOLDOWN + 1)

        with patch("backend.core.redis_manager.RedisManager") as RM:
            mgr = MagicMock()
            mgr.get_sync_client.return_value = healthy
            RM.get_instance.return_value = mgr
            _, info = rl.is_allowed("k-rec", limit=10, window=60)

        assert rl.redis_available is True
        assert info["backend"] == "redis"
        assert rl.metrics["recovery_attempts"] >= 1
        assert rl.metrics["recovery_successes"] == 1

    def test_try_recover_respects_cooldown(self):
        rl = _fresh_limiter(redis_client=None)
        # Recent attempt → another call within cooldown must NOT reconnect.
        rl._last_recovery_attempt = time.time()
        before = rl.metrics["recovery_attempts"]

        with patch("backend.core.redis_manager.RedisManager") as RM:
            mgr = MagicMock()
            RM.get_instance.return_value = mgr
            rl.is_allowed("k-cool", limit=10, window=60)

        assert rl.metrics["recovery_attempts"] == before


class TestStatsShape:
    def test_stats_include_all_metric_keys(self):
        # Clean memory storage so `in_memory_keys` is predictable
        _rate_limit_storage.clear()
        stats = get_rate_limit_stats()
        assert "backend" in stats
        assert "connected" in stats
        assert "rate_limits_configured" in stats
        assert "metrics" in stats
        for k in (
            "redis_requests", "redis_errors", "memory_fallback_requests",
            "recovery_attempts", "recovery_successes",
        ):
            assert k in stats["metrics"]
        assert "last_error" in stats
        assert "in_memory_keys" in stats
        assert "recovery_cooldown_seconds" in stats
