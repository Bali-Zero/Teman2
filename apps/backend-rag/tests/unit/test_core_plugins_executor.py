"""
Unit tests for Plugin Executor
Coverage target: 90%+ (161 statements)
Tests execution, caching, rate limiting, circuit breakers, and metrics
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.plugins.executor import PluginExecutor
from core.plugins.plugin import Plugin, PluginCategory, PluginInput, PluginMetadata, PluginOutput

# ============================================================================
# Mock Plugin Classes
# ============================================================================


class MockPlugin(Plugin):
    """Mock plugin for testing"""

    def __init__(self, name="test.plugin", rate_limit=None, requires_auth=False, estimated_time=5):
        self._name = name
        self._rate_limit = rate_limit
        self._requires_auth = requires_auth
        self._estimated_time = estimated_time
        super().__init__()

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._name,
            description="Test plugin",
            category=PluginCategory.SYSTEM,
            version="1.0.0",
            rate_limit=self._rate_limit,
            requires_auth=self._requires_auth,
            estimated_time=self._estimated_time,
        )

    @property
    def input_schema(self) -> type[PluginInput]:
        return PluginInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        return PluginOutput

    async def execute(self, input_data: PluginInput) -> PluginOutput:
        return PluginOutput(success=True, data={"result": "success"})

    async def validate(self, input_data: PluginInput) -> bool:
        return True


class FailingPlugin(Plugin):
    """Plugin that always fails"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="failing.plugin",
            description="Failing plugin",
            category=PluginCategory.SYSTEM,
            version="1.0.0",
        )

    @property
    def input_schema(self) -> type[PluginInput]:
        return PluginInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        return PluginOutput

    async def execute(self, input_data: PluginInput) -> PluginOutput:
        raise Exception("Plugin execution failed")


class SlowPlugin(Plugin):
    """Plugin that times out"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="slow.plugin",
            description="Slow plugin",
            category=PluginCategory.SYSTEM,
            version="1.0.0",
            estimated_time=0.1,
        )

    @property
    def input_schema(self) -> type[PluginInput]:
        return PluginInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        return PluginOutput

    async def execute(self, input_data: PluginInput) -> PluginOutput:
        await asyncio.sleep(10)
        return PluginOutput(success=True, data={"result": "slow"})


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def executor():
    """Create PluginExecutor instance"""
    return PluginExecutor()


@pytest.fixture
def executor_with_redis():
    """Create PluginExecutor with mock Redis"""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    return PluginExecutor(redis_client=mock_redis)


@pytest.fixture
def mock_plugin():
    """Create mock plugin"""
    return MockPlugin()


@pytest.fixture
def mock_registry():
    """Mock plugin registry"""
    with patch("core.plugins.executor.registry") as mock_reg:
        yield mock_reg


# ============================================================================
# Test Initialization
# ============================================================================


def test_executor_init(executor):
    """Test executor initialization"""
    assert executor.redis is None
    assert len(executor._metrics) == 0
    assert len(executor._rate_limits) == 0
    assert len(executor._circuit_breakers) == 0


def test_executor_init_with_redis(executor_with_redis):
    """Test executor initialization with Redis"""
    assert executor_with_redis.redis is not None


# ============================================================================
# Test Plugin Execution
# ============================================================================


@pytest.mark.asyncio
async def test_execute_plugin_not_found(executor, mock_registry):
    """Test executing non-existent plugin"""
    mock_registry.get.return_value = None

    result = await executor.execute("nonexistent.plugin", {})

    assert result.success is False
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_execute_plugin_success(executor, mock_registry):
    """Test successful plugin execution"""
    plugin = MockPlugin()
    mock_registry.get.return_value = plugin

    result = await executor.execute("test.plugin", {})

    assert result.success is True
    assert result.data["result"] == "success"
    assert "execution_time" in result.metadata
    assert "plugin_version" in result.metadata


@pytest.mark.asyncio
async def test_execute_plugin_with_user_id(executor, mock_registry):
    """Test executing plugin with user ID"""
    plugin = MockPlugin()
    mock_registry.get.return_value = plugin

    result = await executor.execute("test.plugin", {}, user_id="user123")

    assert result.success is True


@pytest.mark.asyncio
async def test_execute_requires_auth_without_user(executor, mock_registry):
    """Test executing auth-required plugin without user"""
    plugin = MockPlugin(requires_auth=True)
    mock_registry.get.return_value = plugin

    result = await executor.execute("test.plugin", {})

    assert result.success is False
    assert "Authentication required" in result.error


@pytest.mark.asyncio
async def test_execute_requires_auth_with_user(executor, mock_registry):
    """Test executing auth-required plugin with user"""
    plugin = MockPlugin(requires_auth=True)
    mock_registry.get.return_value = plugin

    result = await executor.execute("test.plugin", {}, user_id="user123")

    assert result.success is True


# ============================================================================
# Test Rate Limiting
# ============================================================================


@pytest.mark.asyncio
async def test_rate_limit_success(executor, mock_registry):
    """Test rate limiting allows requests within limit"""
    plugin = MockPlugin(rate_limit=10)
    mock_registry.get.return_value = plugin

    # First request should succeed
    result = await executor.execute("test.plugin", {}, user_id="user123")
    assert result.success is True


@pytest.mark.asyncio
async def test_rate_limit_exceeded(executor, mock_registry):
    """Test rate limiting blocks requests exceeding limit"""
    plugin = MockPlugin(rate_limit=2)
    mock_registry.get.return_value = plugin

    # Make 2 requests (within limit)
    await executor.execute("test.plugin", {}, user_id="user123")
    await executor.execute("test.plugin", {}, user_id="user123")

    # Third request should be rate limited
    result = await executor.execute("test.plugin", {}, user_id="user123")

    assert result.success is False
    assert "Rate limit exceeded" in result.error


@pytest.mark.asyncio
async def test_rate_limit_per_user(executor, mock_registry):
    """Test rate limiting is per-user"""
    plugin = MockPlugin(rate_limit=2)
    mock_registry.get.return_value = plugin

    # User1 makes 2 requests
    await executor.execute("test.plugin", {}, user_id="user1")
    await executor.execute("test.plugin", {}, user_id="user1")

    # User2 should still be able to make requests
    result = await executor.execute("test.plugin", {}, user_id="user2")
    assert result.success is True


# ============================================================================
# Test Caching
# ============================================================================


@pytest.mark.asyncio
async def test_cache_miss(executor_with_redis, mock_registry):
    """Test cache miss executes plugin"""
    plugin = MockPlugin()
    mock_registry.get.return_value = plugin
    executor_with_redis.redis.get.return_value = None

    result = await executor_with_redis.execute("test.plugin", {"input": "data"})

    assert result.success is True
    assert executor_with_redis._metrics["test.plugin"]["cache_misses"] == 1


@pytest.mark.asyncio
async def test_cache_hit(executor_with_redis, mock_registry):
    """Test cache hit returns cached result"""
    plugin = MockPlugin()
    mock_registry.get.return_value = plugin

    cached_output = PluginOutput(success=True, data={"cached": "result"})
    executor_with_redis.redis.get.return_value = cached_output.json()

    result = await executor_with_redis.execute("test.plugin", {"input": "data"})

    assert result.success is True
    assert result.data["cached"] == "result"
    assert executor_with_redis._metrics["test.plugin"]["cache_hits"] == 1


@pytest.mark.asyncio
async def test_cache_disabled(executor_with_redis, mock_registry):
    """Test caching can be disabled"""
    plugin = MockPlugin()
    mock_registry.get.return_value = plugin

    result = await executor_with_redis.execute("test.plugin", {}, use_cache=False)

    assert result.success is True
    # Should not check cache
    executor_with_redis.redis.get.assert_not_called()


# ============================================================================
# Test Circuit Breaker
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures(executor, mock_registry):
    """Test circuit breaker opens after 5 failures"""
    plugin = FailingPlugin()
    mock_registry.get.return_value = plugin

    # Make 5 failed requests
    for _ in range(5):
        result = await executor.execute("failing.plugin", {})
        assert result.success is False

    # Circuit should be open now
    result = await executor.execute("failing.plugin", {})
    assert result.success is False
    assert "Service temporarily unavailable" in result.error


@pytest.mark.asyncio
async def test_circuit_breaker_resets_after_cooldown(executor, mock_registry):
    """Test circuit breaker resets after cooldown period"""
    plugin = FailingPlugin()
    mock_registry.get.return_value = plugin

    # Make 5 failures to open circuit
    for _ in range(5):
        await executor.execute("failing.plugin", {})

    # Manually reset cooldown time (simulate 60+ seconds passing)
    executor._circuit_breakers["failing.plugin"]["last_failure_time"] = time.time() - 61

    # Circuit should be reset, execution should proceed (and fail again)
    result = await executor.execute("failing.plugin", {})
    assert "Circuit breaker open" not in result.error


@pytest.mark.asyncio
async def test_circuit_breaker_resets_on_success(executor, mock_registry):
    """Test circuit breaker resets on successful execution"""
    # Create plugin that fails then succeeds
    call_count = [0]

    class FlakeyPlugin(Plugin):
        @property
        def metadata(self) -> PluginMetadata:
            return PluginMetadata(
                name="flakey.plugin",
                description="Flakey plugin",
                category=PluginCategory.SYSTEM,
                version="1.0.0",
            )

        @property
        def input_schema(self) -> type[PluginInput]:
            return PluginInput

        @property
        def output_schema(self) -> type[PluginOutput]:
            return PluginOutput

        async def execute(self, input_data: PluginInput) -> PluginOutput:
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Failed")
            return PluginOutput(success=True, data={"result": "success"})

    plugin = FlakeyPlugin()
    mock_registry.get.return_value = plugin

    # First 2 calls fail
    await executor.execute("flakey.plugin", {})
    await executor.execute("flakey.plugin", {})

    # Third call succeeds
    result = await executor.execute("flakey.plugin", {})
    assert result.success is True

    # Circuit breaker should be reset
    assert "flakey.plugin" not in executor._circuit_breakers


# ============================================================================
# Test Timeout
# ============================================================================


@pytest.mark.asyncio
async def test_timeout_default(executor, mock_registry):
    """Test default timeout based on estimated_time"""
    plugin = SlowPlugin()
    mock_registry.get.return_value = plugin

    result = await executor.execute("slow.plugin", {})

    assert result.success is False
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_timeout_custom(executor, mock_registry):
    """Test custom timeout override"""
    plugin = SlowPlugin()
    mock_registry.get.return_value = plugin

    result = await executor.execute("slow.plugin", {}, timeout=0.1)

    assert result.success is False
    assert "timeout" in result.error.lower()


# ============================================================================
# Test Retry Logic
# ============================================================================


@pytest.mark.asyncio
async def test_retry_success_on_second_attempt(executor, mock_registry):
    """Test retry succeeds on second attempt"""
    call_count = [0]

    class RetryPlugin(Plugin):
        @property
        def metadata(self) -> PluginMetadata:
            return PluginMetadata(
                name="retry.plugin",
                description="Retry plugin",
                category=PluginCategory.SYSTEM,
                version="1.0.0",
            )

        @property
        def input_schema(self) -> type[PluginInput]:
            return PluginInput

        @property
        def output_schema(self) -> type[PluginOutput]:
            return PluginOutput

        async def execute(self, input_data: PluginInput) -> PluginOutput:
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First attempt fails")
            return PluginOutput(success=True, data={"result": "success"})

    plugin = RetryPlugin()
    mock_registry.get.return_value = plugin

    result = await executor.execute("retry.plugin", {}, retry_count=2)

    assert result.success is True
    assert call_count[0] == 2


@pytest.mark.asyncio
async def test_retry_fails_after_all_attempts(executor, mock_registry):
    """Test retry fails after all attempts exhausted"""
    plugin = FailingPlugin()
    mock_registry.get.return_value = plugin

    result = await executor.execute("failing.plugin", {}, retry_count=2)

    assert result.success is False
    assert "after 3 attempts" in result.error


# ============================================================================
# Test Metrics
# ============================================================================


@pytest.mark.asyncio
async def test_metrics_success(executor, mock_registry):
    """Test metrics recorded on success"""
    plugin = MockPlugin()
    mock_registry.get.return_value = plugin

    await executor.execute("test.plugin", {})

    metrics = executor.get_metrics("test.plugin")
    assert metrics["calls"] == 1
    assert metrics["successes"] == 1
    assert metrics["failures"] == 0
    assert metrics["avg_time"] > 0
    assert metrics["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_metrics_failure(executor, mock_registry):
    """Test metrics recorded on failure"""
    plugin = FailingPlugin()
    mock_registry.get.return_value = plugin

    await executor.execute("failing.plugin", {})

    metrics = executor.get_metrics("failing.plugin")
    assert metrics["calls"] == 1
    assert metrics["successes"] == 0
    assert metrics["failures"] == 1
    assert metrics["success_rate"] == 0.0
    assert metrics["last_error"] is not None


@pytest.mark.asyncio
async def test_get_all_metrics(executor, mock_registry):
    """Test getting all plugin metrics"""
    plugin1 = MockPlugin(name="plugin1")
    plugin2 = MockPlugin(name="plugin2")
    mock_registry.get.side_effect = lambda name: plugin1 if name == "plugin1" else plugin2

    await executor.execute("plugin1", {})
    await executor.execute("plugin2", {})

    all_metrics = executor.get_all_metrics()

    assert "plugin1" in all_metrics
    assert "plugin2" in all_metrics
    assert all_metrics["plugin1"]["calls"] == 1
    assert all_metrics["plugin2"]["calls"] == 1


# ============================================================================
# Test Input Validation
# ============================================================================


@pytest.mark.asyncio
async def test_input_validation_failure(executor, mock_registry):
    """Test input validation failure"""

    class StrictPlugin(Plugin):
        @property
        def metadata(self) -> PluginMetadata:
            return PluginMetadata(
                name="strict.plugin",
                description="Strict plugin",
                category=PluginCategory.SYSTEM,
                version="1.0.0",
            )

        @property
        def input_schema(self) -> type[PluginInput]:
            # Require specific fields
            class StrictInput(PluginInput):
                required_field: str

            return StrictInput

        @property
        def output_schema(self) -> type[PluginOutput]:
            return PluginOutput

        async def execute(self, input_data: PluginInput) -> PluginOutput:
            return PluginOutput(success=True)

    plugin = StrictPlugin()
    mock_registry.get.return_value = plugin

    # Missing required_field
    result = await executor.execute("strict.plugin", {})

    assert result.success is False
    assert "Input validation failed" in result.error


# ============================================================================
# Test Warm Up Plugins
# ============================================================================


@pytest.mark.asyncio
async def test_warm_plugins(executor, mock_registry):
    """Test warming up plugins"""
    plugin = MockPlugin()
    plugin.on_load = AsyncMock()
    mock_registry.get.return_value = plugin

    await executor.warm_plugins(["test.plugin"])

    plugin.on_load.assert_called_once()


@pytest.mark.asyncio
async def test_warm_plugins_handles_errors(executor, mock_registry):
    """Test warming up plugins handles errors gracefully"""
    plugin = MockPlugin()
    plugin.on_load = AsyncMock(side_effect=Exception("Load failed"))
    mock_registry.get.return_value = plugin

    # Should not raise exception
    await executor.warm_plugins(["test.plugin"])


# ============================================================================
# Test Cache Key Generation
# ============================================================================


def test_generate_cache_key(executor):
    """Test cache key generation"""
    key1 = executor._generate_cache_key("test.plugin", {"a": 1, "b": 2})
    key2 = executor._generate_cache_key("test.plugin", {"b": 2, "a": 1})

    # Same data in different order should produce same key
    assert key1 == key2

    key3 = executor._generate_cache_key("test.plugin", {"a": 1, "b": 3})

    # Different data should produce different key
    assert key1 != key3


# ============================================================================
# Test Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_execute_with_validation_failure(executor, mock_registry):
    """Test execution with plugin validation failure"""

    class ValidatingPlugin(Plugin):
        @property
        def metadata(self) -> PluginMetadata:
            return PluginMetadata(
                name="validating.plugin",
                description="Validating plugin",
                category=PluginCategory.SYSTEM,
                version="1.0.0",
            )

        @property
        def input_schema(self) -> type[PluginInput]:
            return PluginInput

        @property
        def output_schema(self) -> type[PluginOutput]:
            return PluginOutput

        async def validate(self, input_data: PluginInput) -> bool:
            return False

        async def execute(self, input_data: PluginInput) -> PluginOutput:
            return PluginOutput(success=True)

    plugin = ValidatingPlugin()
    mock_registry.get.return_value = plugin

    result = await executor.execute("validating.plugin", {})

    assert result.success is False
    assert "validation failed" in result.error.lower()


@pytest.mark.asyncio
async def test_metrics_zero_calls(executor):
    """Test metrics with zero calls"""
    metrics = executor.get_metrics("nonexistent.plugin")

    assert metrics["calls"] == 0
    assert metrics["avg_time"] == 0.0
    assert metrics["success_rate"] == 0.0
    assert metrics["cache_hit_rate"] == 0.0


@pytest.mark.asyncio
async def test_cache_error_handling(executor_with_redis, mock_registry):
    """Test cache error handling"""
    plugin = MockPlugin()
    mock_registry.get.return_value = plugin
    executor_with_redis.redis.get.side_effect = Exception("Redis error")

    # Should still execute despite cache error
    result = await executor_with_redis.execute("test.plugin", {})

    assert result.success is True
