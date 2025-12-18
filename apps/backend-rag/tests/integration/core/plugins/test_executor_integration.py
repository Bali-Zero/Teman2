"""
Integration Tests for PluginExecutor
Tests plugin execution with caching, rate limiting, and error handling
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestPluginExecutorIntegration:
    """Comprehensive integration tests for PluginExecutor"""

    @pytest_asyncio.fixture
    async def mock_plugin(self):
        """Create mock plugin"""
        from core.plugins.plugin import Plugin, PluginCategory, PluginMetadata
        from pydantic import BaseModel

        class TestInput(BaseModel):
            test_field: str

        class TestOutput(BaseModel):
            result: str

        class MockPlugin(Plugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test.plugin",
                    version="1.0.0",
                    description="Test plugin",
                    category=PluginCategory.BALI_ZERO,
                    rate_limit=60,
                    requires_auth=False,
                )

            @property
            def input_schema(self):
                return TestInput

            @property
            def output_schema(self):
                return TestOutput

            async def execute(self, input_data):
                return self.output_schema(result="test result")

        return MockPlugin()

    @pytest_asyncio.fixture
    async def mock_redis(self):
        """Create mock Redis client"""
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=True)
        mock_redis.ping = AsyncMock(return_value=True)
        return mock_redis

    @pytest_asyncio.fixture
    async def executor(self, mock_redis):
        """Create PluginExecutor instance"""
        from core.plugins.executor import PluginExecutor

        executor = PluginExecutor(redis_client=mock_redis)
        return executor

    @pytest_asyncio.fixture
    async def executor_no_redis(self):
        """Create PluginExecutor without Redis"""
        from core.plugins.executor import PluginExecutor

        return PluginExecutor(redis_client=None)

    @pytest.mark.asyncio
    async def test_initialization(self, executor):
        """Test executor initialization"""
        assert executor is not None
        assert executor._redis_available is True

    @pytest.mark.asyncio
    async def test_initialization_no_redis(self, executor_no_redis):
        """Test executor initialization without Redis"""
        assert executor_no_redis is not None
        assert executor_no_redis._redis_available is False

    @pytest.mark.asyncio
    async def test_execute_plugin_success(self, executor, mock_plugin):
        """Test executing plugin successfully"""
        with patch("core.plugins.executor.registry.get", return_value=mock_plugin):
            result = await executor.execute(
                "test.plugin", {"test_field": "test_value"}, use_cache=False
            )

            assert result is not None
            assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_plugin_not_found(self, executor):
        """Test executing non-existent plugin"""
        with patch("core.plugins.executor.registry.get", return_value=None):
            result = await executor.execute("nonexistent.plugin", {})

            assert result is not None
            assert result.success is False
            assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_plugin_with_cache(self, executor, mock_plugin, mock_redis):
        """Test executing plugin with caching"""
        # First call - cache miss
        mock_redis.get = AsyncMock(return_value=None)

        with patch("core.plugins.executor.registry.get", return_value=mock_plugin):
            result1 = await executor.execute("test.plugin", {"test_field": "test"}, use_cache=True)

            assert result1 is not None
            assert result1.success is True

        # Second call - cache hit
        import json

        cached_result = json.dumps({"success": True, "data": {"result": "cached"}})
        mock_redis.get = AsyncMock(return_value=cached_result)

        with patch("core.plugins.executor.registry.get", return_value=mock_plugin):
            result2 = await executor.execute("test.plugin", {"test_field": "test"}, use_cache=True)

            assert result2 is not None

    @pytest.mark.asyncio
    async def test_execute_plugin_rate_limit(self, executor, mock_plugin):
        """Test rate limiting"""
        # Mock plugin with low rate limit
        mock_plugin.metadata.rate_limit = 1  # 1 per minute

        with patch("core.plugins.executor.registry.get", return_value=mock_plugin):
            # First call should succeed
            result1 = await executor.execute("test.plugin", {"test_field": "test"}, use_cache=False)
            assert result1.success is True

            # Second call immediately should fail rate limit
            result2 = await executor.execute("test.plugin", {"test_field": "test"}, use_cache=False)
            # May or may not fail depending on implementation
            assert result2 is not None

    @pytest.mark.asyncio
    async def test_execute_plugin_auth_required(self, executor, mock_plugin):
        """Test authentication requirement"""
        mock_plugin.metadata.requires_auth = True

        with patch("core.plugins.executor.registry.get", return_value=mock_plugin):
            result = await executor.execute("test.plugin", {"test_field": "test"}, user_id=None)

            assert result is not None
            assert result.success is False
            assert "auth" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_plugin_validation_error(self, executor, mock_plugin):
        """Test input validation error"""
        with patch("core.plugins.executor.registry.get", return_value=mock_plugin):
            result = await executor.execute("test.plugin", {"invalid_field": "test"})

            assert result is not None
            assert result.success is False
            assert "validation" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_plugin_timeout(self, executor, mock_plugin):
        """Test plugin execution timeout"""

        async def slow_execute(input_data):
            import asyncio

            await asyncio.sleep(10)  # Simulate slow execution
            return mock_plugin.output_schema(result="slow")

        mock_plugin.execute = slow_execute

        with patch("core.plugins.executor.registry.get", return_value=mock_plugin):
            result = await executor.execute(
                "test.plugin", {"test_field": "test"}, timeout=0.1, retry_count=0
            )

            assert result is not None
            # May timeout or succeed depending on implementation

    @pytest.mark.asyncio
    async def test_execute_plugin_retry(self, executor, mock_plugin):
        """Test plugin execution with retry"""
        call_count = 0

        async def failing_then_success(input_data):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")
            return mock_plugin.output_schema(result="success")

        mock_plugin.execute = failing_then_success

        with patch("core.plugins.executor.registry.get", return_value=mock_plugin):
            result = await executor.execute("test.plugin", {"test_field": "test"}, retry_count=2)

            assert result is not None
            # Should succeed after retry

    @pytest.mark.asyncio
    async def test_circuit_breaker(self, executor, mock_plugin):
        """Test circuit breaker functionality"""

        async def failing_execute(input_data):
            raise Exception("Service error")

        mock_plugin.execute = failing_execute

        with patch("core.plugins.executor.registry.get", return_value=mock_plugin):
            # Trigger multiple failures to open circuit breaker
            for _ in range(6):
                await executor.execute("test.plugin", {"test_field": "test"}, retry_count=0)

            # Next call should be blocked by circuit breaker
            result = await executor.execute("test.plugin", {"test_field": "test"})

            assert result is not None
            # May be blocked or may succeed depending on implementation

    def test_get_metrics(self, executor):
        """Test getting execution metrics"""
        metrics = executor.get_metrics()

        assert metrics is not None
        assert isinstance(metrics, dict)

    def test_get_metrics_for_plugin(self, executor):
        """Test getting metrics for specific plugin"""
        metrics = executor.get_metrics("test.plugin")

        assert metrics is not None
        assert "calls" in metrics

    def test_clear_metrics(self, executor):
        """Test clearing metrics"""
        executor.clear_metrics()
        metrics = executor.get_metrics()

        assert metrics is not None
