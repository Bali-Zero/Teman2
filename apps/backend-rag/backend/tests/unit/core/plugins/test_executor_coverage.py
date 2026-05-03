"""
Unit tests for backend/core/plugins/executor.py
Covers: PluginExecutor — execute, cache, rate_limit, circuit_breaker, metrics
"""

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.plugins.plugin import (
    Plugin,
    PluginCategory,
    PluginInput,
    PluginMetadata,
    PluginOutput,
)
from backend.core.plugins.executor import (
    CIRCUIT_BREAKER_COOLDOWN_SECONDS,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    PluginExecutor,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_plugin(
    name: str = "test.plugin",
    rate_limit: int | None = None,
    requires_auth: bool = False,
    estimated_time: float = 1.0,
    execute_result: PluginOutput | None = None,
    execute_side_effect=None,
) -> Plugin:
    meta = PluginMetadata(
        name=name,
        version="1.0.0",
        description=f"Plugin {name}",
        category=PluginCategory.GENERAL,
        rate_limit=rate_limit,
        requires_auth=requires_auth,
        estimated_time=estimated_time,
    )

    class ConcretePlugin(Plugin):
        @property
        def metadata(self) -> PluginMetadata:
            return meta

        @property
        def input_schema(self) -> type[PluginInput]:
            return PluginInput

        @property
        def output_schema(self) -> type[PluginOutput]:
            return PluginOutput

        async def execute(self, input_data: PluginInput) -> PluginOutput:
            if execute_side_effect:
                raise execute_side_effect
            return execute_result or PluginOutput(success=True, data={"result": "ok"})

    plugin = ConcretePlugin()
    return plugin


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def executor():
    return PluginExecutor()


@pytest.fixture
def executor_with_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.ping = AsyncMock(return_value=True)
    return PluginExecutor(redis_client=redis), redis


# ─────────────────────────────────────────────────────────────────────────────
# __init__
# ─────────────────────────────────────────────────────────────────────────────

def test_executor_init_without_redis(executor):
    assert executor.redis is None
    assert executor._redis_available is False


def test_executor_init_with_redis(executor_with_redis):
    exe, redis = executor_with_redis
    assert exe.redis is redis
    assert exe._redis_available is True


# ─────────────────────────────────────────────────────────────────────────────
# execute — plugin not found
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_plugin_not_found(executor):
    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = None
        result = await executor.execute("nonexistent", {})
    assert result.success is False
    assert "not found" in result.error.lower()


# ─────────────────────────────────────────────────────────────────────────────
# execute — auth check
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_requires_auth_no_user_id(executor):
    plugin = _make_plugin(name="auth.plugin", requires_auth=True)
    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await executor.execute("auth.plugin", {}, user_id=None)
    assert result.success is False
    assert "auth" in result.error.lower()


@pytest.mark.asyncio
async def test_execute_requires_auth_with_user_id(executor):
    plugin = _make_plugin(name="auth.plugin2", requires_auth=True)
    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await executor.execute("auth.plugin2", {}, user_id="user123")
    assert result.success is True


# ─────────────────────────────────────────────────────────────────────────────
# execute — input validation failure
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_input_validation_failure(executor):
    """Test that invalid input schema raises and returns error."""
    plugin = _make_plugin(name="validate.plugin")

    # Override input_schema to raise on instantiation
    class StrictInput(PluginInput):
        required_field: str

        class Config:
            extra = "forbid"

    plugin.__class__.input_schema = property(lambda self: StrictInput)

    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        # Missing required_field
        result = await executor.execute("validate.plugin", {})

    assert result.success is False
    assert "validation" in result.error.lower()


# ─────────────────────────────────────────────────────────────────────────────
# execute — successful execution
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_success(executor):
    plugin = _make_plugin(name="success.plugin")
    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await executor.execute("success.plugin", {})
    assert result.success is True
    assert "execution_time" in result.metadata
    assert "plugin_version" in result.metadata


# ─────────────────────────────────────────────────────────────────────────────
# execute — retry logic
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_retry_on_failure(executor):
    """Plugin fails once, succeeds on retry."""
    call_count = 0

    class FlakeyPlugin(Plugin):
        @property
        def metadata(self) -> PluginMetadata:
            return PluginMetadata(
                name="flakey.plugin",
                version="1.0.0",
                description="Flakey",
                category=PluginCategory.GENERAL,
                estimated_time=0.01,
            )

        @property
        def input_schema(self):
            return PluginInput

        @property
        def output_schema(self):
            return PluginOutput

        async def execute(self, input_data):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("transient failure")
            return PluginOutput(success=True)

    plugin = FlakeyPlugin()

    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await executor.execute("flakey.plugin", {}, retry_count=2)

    assert result.success is True


@pytest.mark.asyncio
async def test_execute_max_retries_exhausted(executor):
    plugin = _make_plugin(name="always.fail", execute_side_effect=RuntimeError("always fails"))
    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await executor.execute("always.fail", {}, retry_count=2)
    assert result.success is False
    assert "3 attempts" in result.error


@pytest.mark.asyncio
async def test_execute_timeout_retry(executor):
    """TimeoutError triggers retry."""
    call_count = 0

    class TimeoutPlugin(Plugin):
        @property
        def metadata(self):
            return PluginMetadata(
                name="timeout.plugin",
                version="1.0.0",
                description="Times out",
                category=PluginCategory.GENERAL,
                estimated_time=0.01,
            )

        @property
        def input_schema(self):
            return PluginInput

        @property
        def output_schema(self):
            return PluginOutput

        async def execute(self, input_data):
            nonlocal call_count
            call_count += 1
            raise asyncio.TimeoutError()

    plugin = TimeoutPlugin()
    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await executor.execute("timeout.plugin", {}, retry_count=1)

    assert result.success is False
    assert "timeout" in result.error.lower()


# ─────────────────────────────────────────────────────────────────────────────
# execute — circuit breaker
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_circuit_breaker_open(executor):
    """Circuit breaker rejects requests when open."""
    plugin = _make_plugin(name="circuit.plugin")

    # Force circuit breaker open
    executor._circuit_breakers["circuit.plugin"] = {
        "failures": CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        "last_failure_time": time.time(),  # Just failed
    }

    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await executor.execute("circuit.plugin", {})

    assert result.success is False
    assert "circuit breaker" in result.error.lower()


@pytest.mark.asyncio
async def test_execute_circuit_breaker_resets_after_cooldown(executor):
    """Circuit breaker resets after cooldown period."""
    plugin = _make_plugin(name="circuit.reset")

    # Force circuit breaker to have expired cooldown
    executor._circuit_breakers["circuit.reset"] = {
        "failures": CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        "last_failure_time": time.time() - (CIRCUIT_BREAKER_COOLDOWN_SECONDS + 1),
    }

    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await executor.execute("circuit.reset", {})

    # Circuit breaker should have reset, plugin executes successfully
    assert result.success is True
    assert "circuit.reset" not in executor._circuit_breakers


# ─────────────────────────────────────────────────────────────────────────────
# execute — rate limiting (memory)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_rate_limit_exceeded(executor):
    plugin = _make_plugin(name="ratelimit.plugin", rate_limit=2)

    # Pre-fill rate limit
    now = time.time()
    executor._rate_limits["ratelimit.plugin"] = [now - 10, now - 5]  # 2 recent calls

    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await executor.execute("ratelimit.plugin", {})

    assert result.success is False
    assert "rate limit" in result.error.lower()


@pytest.mark.asyncio
async def test_execute_rate_limit_ok_when_not_exceeded(executor):
    plugin = _make_plugin(name="ratelimit.ok", rate_limit=10)

    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await executor.execute("ratelimit.ok", {})

    assert result.success is True


@pytest.mark.asyncio
async def test_execute_rate_limit_clears_old_timestamps(executor):
    """Old timestamps (>60s) are purged before checking rate limit."""
    plugin = _make_plugin(name="ratelimit.purge", rate_limit=2)

    # Add old timestamps (>60s ago)
    old_time = time.time() - 70
    executor._rate_limits["ratelimit.purge"] = [old_time, old_time, old_time]

    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await executor.execute("ratelimit.purge", {})

    assert result.success is True


# ─────────────────────────────────────────────────────────────────────────────
# execute — caching
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_cache_hit(executor_with_redis):
    exe, redis = executor_with_redis
    plugin = _make_plugin(name="cache.hit")

    cached_output = PluginOutput(success=True, data={"cached": True})
    redis.get = AsyncMock(return_value=cached_output.json())

    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await exe.execute("cache.hit", {"q": "test"}, use_cache=True)

    assert result.success is True
    assert exe._metrics["cache.hit"]["cache_hits"] == 1


@pytest.mark.asyncio
async def test_execute_cache_miss_writes_cache(executor_with_redis):
    exe, redis = executor_with_redis
    plugin = _make_plugin(name="cache.miss")
    redis.get = AsyncMock(return_value=None)

    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await exe.execute("cache.miss", {}, use_cache=True)

    assert result.success is True
    redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_execute_no_cache_when_disabled(executor_with_redis):
    exe, redis = executor_with_redis
    plugin = _make_plugin(name="cache.disabled")

    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        result = await exe.execute("cache.disabled", {}, use_cache=False)

    assert result.success is True
    redis.get.assert_not_called()
    redis.setex.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# _generate_cache_key
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_cache_key_deterministic(executor):
    key1 = executor._generate_cache_key("test.plugin", {"a": 1, "b": 2})
    key2 = executor._generate_cache_key("test.plugin", {"b": 2, "a": 1})
    assert key1 == key2  # sort_keys=True


def test_generate_cache_key_different_inputs(executor):
    key1 = executor._generate_cache_key("test.plugin", {"a": 1})
    key2 = executor._generate_cache_key("test.plugin", {"a": 2})
    assert key1 != key2


# ─────────────────────────────────────────────────────────────────────────────
# _check_rate_limit — Redis path
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_rate_limit_redis_ok(executor_with_redis):
    exe, redis = executor_with_redis
    redis.incr = AsyncMock(return_value=1)
    result = await exe._check_rate_limit("test.plugin", 5)
    assert result is True


@pytest.mark.asyncio
async def test_check_rate_limit_redis_exceeded(executor_with_redis):
    exe, redis = executor_with_redis
    redis.incr = AsyncMock(return_value=10)
    result = await exe._check_rate_limit("test.plugin", 5)
    assert result is False


@pytest.mark.asyncio
async def test_check_rate_limit_redis_failure_fallback(executor_with_redis):
    """Redis failure falls back to in-memory rate limiting."""
    exe, redis = executor_with_redis
    redis.incr = AsyncMock(side_effect=ConnectionError("redis down"))
    result = await exe._check_rate_limit("test.plugin", 100)
    assert result is True  # In-memory allows (no prior calls)


# ─────────────────────────────────────────────────────────────────────────────
# _is_circuit_broken
# ─────────────────────────────────────────────────────────────────────────────

def test_is_circuit_broken_no_entry(executor):
    assert executor._is_circuit_broken("unknown") is False


def test_is_circuit_broken_below_threshold(executor):
    executor._circuit_breakers["test"] = {
        "failures": CIRCUIT_BREAKER_FAILURE_THRESHOLD - 1,
        "last_failure_time": time.time(),
    }
    assert executor._is_circuit_broken("test") is False


def test_is_circuit_broken_above_threshold_recent(executor):
    executor._circuit_breakers["test"] = {
        "failures": CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        "last_failure_time": time.time(),
    }
    assert executor._is_circuit_broken("test") is True


def test_is_circuit_broken_resets_after_cooldown(executor):
    executor._circuit_breakers["test"] = {
        "failures": CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        "last_failure_time": time.time() - (CIRCUIT_BREAKER_COOLDOWN_SECONDS + 1),
    }
    assert executor._is_circuit_broken("test") is False
    assert "test" not in executor._circuit_breakers


# ─────────────────────────────────────────────────────────────────────────────
# _record_success / _record_failure
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_success_updates_metrics(executor):
    await executor._record_success("test.plugin", 0.5)
    m = executor._metrics["test.plugin"]
    assert m["calls"] == 1
    assert m["successes"] == 1
    assert m["total_time"] == 0.5


@pytest.mark.asyncio
async def test_record_failure_updates_metrics(executor):
    await executor._record_failure("test.plugin", "some error")
    m = executor._metrics["test.plugin"]
    assert m["calls"] == 1
    assert m["failures"] == 1
    assert m["last_error"] == "some error"


@pytest.mark.asyncio
async def test_record_failure_updates_circuit_breaker(executor):
    for _ in range(CIRCUIT_BREAKER_FAILURE_THRESHOLD):
        await executor._record_failure("test.plugin", "error")
    assert "test.plugin" in executor._circuit_breakers
    assert executor._circuit_breakers["test.plugin"]["failures"] >= CIRCUIT_BREAKER_FAILURE_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
# get_metrics
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_metrics_no_calls(executor):
    metrics = executor.get_metrics("no.calls")
    assert metrics["avg_time"] == 0.0
    assert metrics["success_rate"] == 0.0
    assert metrics["cache_hit_rate"] == 0.0


@pytest.mark.asyncio
async def test_get_metrics_with_calls(executor):
    await executor._record_success("metrics.plugin", 1.0)
    await executor._record_success("metrics.plugin", 2.0)
    metrics = executor.get_metrics("metrics.plugin")
    assert metrics["avg_time"] == 1.5
    assert metrics["success_rate"] == 1.0


def test_get_all_metrics(executor):
    executor._metrics["plugin.a"]["calls"] = 5
    executor._metrics["plugin.b"]["calls"] = 3
    all_m = executor.get_all_metrics()
    assert "plugin.a" in all_m
    assert "plugin.b" in all_m


# ─────────────────────────────────────────────────────────────────────────────
# warm_plugins
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_warm_plugins(executor):
    plugin = _make_plugin(name="warm.plugin")
    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        await executor.warm_plugins(["warm.plugin"])


@pytest.mark.asyncio
async def test_warm_plugins_not_found(executor):
    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = None
        # Should not raise
        await executor.warm_plugins(["missing.plugin"])


@pytest.mark.asyncio
async def test_warm_plugins_on_load_failure(executor):
    plugin = _make_plugin(name="warm.fail")
    plugin.on_load = AsyncMock(side_effect=RuntimeError("on_load error"))
    with patch("backend.core.plugins.executor.registry") as mock_registry:
        mock_registry.get.return_value = plugin
        # Should not raise
        await executor.warm_plugins(["warm.fail"])


# ─────────────────────────────────────────────────────────────────────────────
# _get_cached / _cache_result
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_cached_no_redis(executor):
    result = await executor._get_cached("test.plugin", {})
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_redis_none(executor_with_redis):
    exe, redis = executor_with_redis
    redis.get = AsyncMock(return_value=None)
    result = await exe._get_cached("test.plugin", {})
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_redis_hit(executor_with_redis):
    exe, redis = executor_with_redis
    output = PluginOutput(success=True, data="cached_data")
    redis.get = AsyncMock(return_value=output.json())
    result = await exe._get_cached("test.plugin", {"q": "x"})
    assert result is not None
    assert result.success is True


@pytest.mark.asyncio
async def test_cache_result_no_redis(executor):
    # Should not raise
    output = PluginOutput(success=True)
    await executor._cache_result("test.plugin", {}, output)


@pytest.mark.asyncio
async def test_cache_result_with_redis(executor_with_redis):
    exe, redis = executor_with_redis
    output = PluginOutput(success=True)
    await exe._cache_result("test.plugin", {"a": 1}, output)
    redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_cache_result_redis_error_is_handled(executor_with_redis):
    exe, redis = executor_with_redis
    redis.setex = AsyncMock(side_effect=ConnectionError("redis down"))
    output = PluginOutput(success=True)
    # Should not raise
    await exe._cache_result("test.plugin", {}, output)
