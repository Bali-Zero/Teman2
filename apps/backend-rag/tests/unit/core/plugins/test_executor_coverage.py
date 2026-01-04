import asyncio
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.plugins.executor import (
    CIRCUIT_BREAKER_COOLDOWN_SECONDS,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    PluginExecutor,
)
from core.plugins.plugin import Plugin, PluginCategory, PluginInput, PluginMetadata, PluginOutput


class DummyInput(PluginInput):
    value: int


class DummyOutput(PluginOutput):
    pass


class DummyPlugin(Plugin):
    def __init__(
        self,
        *,
        name: str = "dummy.plugin",
        rate_limit: int | None = None,
        requires_auth: bool = False,
        estimated_time: float = 1.0,
        validate_result: bool = True,
        execute_result: PluginOutput | None = None,
        execute_side_effect: Exception | None = None,
    ):
        self._metadata = PluginMetadata(
            name=name,
            description="dummy",
            category=PluginCategory.SYSTEM,
            rate_limit=rate_limit,
            requires_auth=requires_auth,
            estimated_time=estimated_time,
        )
        self._validate_result = validate_result
        self._execute_result = execute_result or DummyOutput(success=True, data={"ok": True})
        self._execute_side_effect = execute_side_effect
        super().__init__()

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    @property
    def input_schema(self) -> type[PluginInput]:
        return DummyInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        return DummyOutput

    async def execute(self, input_data: PluginInput) -> PluginOutput:
        if self._execute_side_effect:
            raise self._execute_side_effect
        return self._execute_result

    async def validate(self, _input_data: PluginInput) -> bool:
        return self._validate_result


@pytest.mark.asyncio
async def test_execute_plugin_not_found():
    executor = PluginExecutor()
    with patch("core.plugins.executor.registry.get", return_value=None):
        result = await executor.execute("missing.plugin", {"value": 1}, user_id="user")
    assert result.success is False
    assert result.error == "Plugin not found"


@pytest.mark.asyncio
async def test_execute_circuit_breaker_open():
    executor = PluginExecutor()
    plugin = DummyPlugin()
    executor._circuit_breakers[plugin.metadata.name] = {
        "failures": CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        "last_failure_time": 100.0,
    }
    with patch("core.plugins.executor.registry.get", return_value=plugin):
        with patch("core.plugins.executor.time.time", return_value=100.0 + 1):
            result = await executor.execute(plugin.metadata.name, {"value": 1}, user_id="user")
    assert result.success is False
    assert "circuit breaker" in result.error


@pytest.mark.asyncio
async def test_execute_rate_limit_exceeded():
    executor = PluginExecutor()
    plugin = DummyPlugin(rate_limit=1)
    with patch("core.plugins.executor.registry.get", return_value=plugin):
        with patch.object(executor, "_check_rate_limit", AsyncMock(return_value=False)):
            result = await executor.execute(plugin.metadata.name, {"value": 1}, user_id="user")
    assert result.success is False
    assert result.metadata["rate_limit"] == 1


@pytest.mark.asyncio
async def test_execute_requires_auth():
    executor = PluginExecutor()
    plugin = DummyPlugin(requires_auth=True)
    with patch("core.plugins.executor.registry.get", return_value=plugin):
        result = await executor.execute(plugin.metadata.name, {"value": 1})
    assert result.success is False
    assert result.error == "Authentication required"


@pytest.mark.asyncio
async def test_execute_input_validation_failure():
    executor = PluginExecutor()
    plugin = DummyPlugin()
    with patch("core.plugins.executor.registry.get", return_value=plugin):
        result = await executor.execute(plugin.metadata.name, {"value": "nope"}, user_id="user")
    assert result.success is False
    assert "Input validation failed" in result.error


@pytest.mark.asyncio
async def test_execute_cache_hit_short_circuits():
    executor = PluginExecutor(redis_client=MagicMock())
    plugin = DummyPlugin()
    cached = PluginOutput(success=True, data={"cached": True})
    with patch("core.plugins.executor.registry.get", return_value=plugin):
        with patch.object(executor, "_get_cached", AsyncMock(return_value=cached)):
            with patch.object(executor, "_execute_with_monitoring", AsyncMock()):
                result = await executor.execute(plugin.metadata.name, {"value": 1}, user_id="user")
    assert result is cached
    assert executor._metrics[plugin.metadata.name]["cache_hits"] == 1


@pytest.mark.asyncio
async def test_execute_success_cache_write_and_circuit_reset():
    executor = PluginExecutor(redis_client=MagicMock())
    plugin = DummyPlugin()
    executor._circuit_breakers[plugin.metadata.name] = {"failures": 1, "last_failure_time": 0}
    result_output = PluginOutput(success=True, data={"ok": True})
    with patch("core.plugins.executor.registry.get", return_value=plugin):
        with patch.object(
            executor, "_execute_with_monitoring", AsyncMock(return_value=result_output)
        ):
            with patch.object(executor, "_cache_result", AsyncMock()) as cache_result:
                result = await executor.execute(plugin.metadata.name, {"value": 1}, user_id="user")
    assert result.success is True
    assert plugin.metadata.name not in executor._circuit_breakers
    cache_result.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_timeout_retry_exhausted():
    executor = PluginExecutor()
    plugin = DummyPlugin()
    with patch("core.plugins.executor.registry.get", return_value=plugin):
        with patch.object(
            executor, "_execute_with_monitoring", AsyncMock(side_effect=asyncio.TimeoutError)
        ):
            with patch("core.plugins.executor.asyncio.sleep", AsyncMock()) as sleeper:
                result = await executor.execute(
                    plugin.metadata.name, {"value": 1}, user_id="user", retry_count=1
                )
    assert result.success is False
    assert result.error == "Plugin execution timeout after 2 attempts"
    assert result.metadata["attempts"] == 2
    assert sleeper.await_count == 1


@pytest.mark.asyncio
async def test_execute_failure_retry_exhausted():
    executor = PluginExecutor()
    plugin = DummyPlugin()
    with patch("core.plugins.executor.registry.get", return_value=plugin):
        with patch.object(
            executor, "_execute_with_monitoring", AsyncMock(side_effect=RuntimeError("boom"))
        ):
            with patch("core.plugins.executor.asyncio.sleep", AsyncMock()) as sleeper:
                result = await executor.execute(
                    plugin.metadata.name, {"value": 1}, user_id="user", retry_count=1
                )
    assert result.success is False
    assert "Plugin execution failed after 2 attempts" in result.error
    assert result.metadata["attempts"] == 2
    assert sleeper.await_count == 1


@pytest.mark.asyncio
async def test_execute_keyboard_interrupt_propagates():
    executor = PluginExecutor()
    plugin = DummyPlugin()
    with patch("core.plugins.executor.registry.get", return_value=plugin):
        with patch.object(
            executor, "_execute_with_monitoring", AsyncMock(side_effect=KeyboardInterrupt)
        ):
            with pytest.raises(KeyboardInterrupt):
                await executor.execute(plugin.metadata.name, {"value": 1}, user_id="user")


@pytest.mark.asyncio
async def test_execute_cache_miss_tracks_metric():
    executor = PluginExecutor(redis_client=MagicMock())
    plugin = DummyPlugin()
    result_output = PluginOutput(success=True, data={"ok": True})
    with patch("core.plugins.executor.registry.get", return_value=plugin):
        with patch.object(executor, "_get_cached", AsyncMock(return_value=None)):
            with patch.object(
                executor, "_execute_with_monitoring", AsyncMock(return_value=result_output)
            ):
                result = await executor.execute(plugin.metadata.name, {"value": 1}, user_id="user")
    assert result.success is True
    assert executor._metrics[plugin.metadata.name]["cache_misses"] == 1


@pytest.mark.asyncio
async def test_execute_with_monitoring_success_metadata():
    executor = PluginExecutor()
    plugin = DummyPlugin()
    times = deque([100.0, 101.5, 105.0, 110.0])
    with patch("core.plugins.executor.time.time", side_effect=lambda: times.popleft()):
        result = await executor._execute_with_monitoring(plugin, DummyInput(value=1))
    assert result.success is True
    assert result.metadata["execution_time"] == 1.5
    assert result.metadata["plugin_version"] == plugin.metadata.version
    assert result.metadata["timestamp"] == 110.0


@pytest.mark.asyncio
async def test_execute_with_monitoring_validation_fails():
    executor = PluginExecutor()
    plugin = DummyPlugin(validate_result=False)
    result = await executor._execute_with_monitoring(plugin, DummyInput(value=1))
    assert result.success is False
    assert result.error == "Input validation failed"


@pytest.mark.asyncio
async def test_execute_with_monitoring_timeout():
    executor = PluginExecutor()
    plugin = DummyPlugin(estimated_time=2.0)

    async def fake_wait_for(_coro, timeout=None):
        _coro.close()
        raise asyncio.TimeoutError

    with patch("core.plugins.executor.asyncio.wait_for", fake_wait_for):
        result = await executor._execute_with_monitoring(plugin, DummyInput(value=1))
    assert result.success is False
    assert "Plugin execution timeout" in result.error
    assert result.metadata["execution_time"] >= 0.0


@pytest.mark.asyncio
async def test_execute_with_monitoring_exception_raises():
    executor = PluginExecutor()
    plugin = DummyPlugin(execute_side_effect=ValueError("bad"))
    with pytest.raises(ValueError):
        await executor._execute_with_monitoring(plugin, DummyInput(value=1))
    assert executor._metrics[plugin.metadata.name]["failures"] == 1
    assert executor._circuit_breakers[plugin.metadata.name]["failures"] == 1


@pytest.mark.asyncio
async def test_check_rate_limit_redis_paths():
    redis = MagicMock()
    redis.incr = AsyncMock(side_effect=[1, 3])
    redis.expire = AsyncMock(return_value=True)
    executor = PluginExecutor(redis_client=redis)

    allowed = await executor._check_rate_limit("plugin", 2, user_id="user")
    denied = await executor._check_rate_limit("plugin", 2, user_id="user")

    assert allowed is True
    assert denied is False
    redis.expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_rate_limit_fallback_to_memory():
    redis = MagicMock()
    redis.incr = AsyncMock(side_effect=RuntimeError("redis down"))
    executor = PluginExecutor(redis_client=redis)
    with patch("core.plugins.executor.time.time", return_value=100.0):
        allowed = await executor._check_rate_limit("plugin", 1, user_id=None)
        denied = await executor._check_rate_limit("plugin", 1, user_id=None)
    assert allowed is True
    assert denied is False


@pytest.mark.asyncio
async def test_get_cached_success_and_error():
    output = PluginOutput(success=True, data={"ok": True})
    redis = MagicMock()
    redis.get = AsyncMock(return_value=output.json())
    executor = PluginExecutor(redis_client=redis)
    cached = await executor._get_cached("plugin", {"value": 1})
    assert cached
    assert cached.data == {"ok": True}

    redis.get = AsyncMock(return_value="not-json")
    cached_error = await executor._get_cached("plugin", {"value": 1})
    assert cached_error is None


@pytest.mark.asyncio
async def test_cache_result_success_and_error():
    redis = MagicMock()
    redis.setex = AsyncMock(return_value=True)
    executor = PluginExecutor(redis_client=redis)
    output = PluginOutput(success=True, data={"ok": True})
    await executor._cache_result("plugin", {"value": 1}, output)
    redis.setex.assert_awaited_once()

    redis.setex = AsyncMock(side_effect=RuntimeError("write error"))
    await executor._cache_result("plugin", {"value": 1}, output)


@pytest.mark.asyncio
async def test_cache_and_get_skip_without_redis():
    executor = PluginExecutor(redis_client=None)
    output = PluginOutput(success=True, data={"ok": True})
    cached = await executor._get_cached("plugin", {"value": 1})
    assert cached is None
    await executor._cache_result("plugin", {"value": 1}, output)


def test_generate_cache_key_deterministic():
    executor = PluginExecutor()
    first = executor._generate_cache_key("plugin", {"b": 2, "a": 1})
    second = executor._generate_cache_key("plugin", {"a": 1, "b": 2})
    assert first == second
    assert first.startswith("plugin:plugin:")


@pytest.mark.asyncio
async def test_record_success_failure_and_metrics():
    executor = PluginExecutor()
    with patch("core.plugins.executor.time.time", return_value=10.0):
        await executor._record_success("plugin", 2.0)
        await executor._record_failure("plugin", "boom")

    executor._metrics["plugin"]["cache_hits"] = 1
    metrics = executor.get_metrics("plugin")
    assert metrics["calls"] == 2
    assert metrics["avg_time"] == 1.0
    assert metrics["success_rate"] == 0.5
    assert metrics["cache_hit_rate"] == 0.5

    empty_metrics = executor.get_metrics("missing")
    assert empty_metrics["avg_time"] == 0.0
    assert empty_metrics["success_rate"] == 0.0
    assert empty_metrics["cache_hit_rate"] == 0.0

    failure_only = PluginExecutor()
    with patch("core.plugins.executor.time.time", return_value=20.0):
        await failure_only._record_failure("fail.plugin", "boom")
    failure_metrics = failure_only.get_metrics("fail.plugin")
    assert failure_metrics["cache_hit_rate"] == 0.0

    all_metrics = executor.get_all_metrics()
    assert "plugin" in all_metrics


def test_is_circuit_broken_reset():
    executor = PluginExecutor()
    executor._circuit_breakers["plugin"] = {
        "failures": CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        "last_failure_time": 0.0,
    }
    with patch(
        "core.plugins.executor.time.time",
        return_value=CIRCUIT_BREAKER_COOLDOWN_SECONDS + 1.0,
    ):
        broken = executor._is_circuit_broken("plugin")
    assert broken is False
    assert "plugin" not in executor._circuit_breakers


@pytest.mark.asyncio
async def test_warm_plugins_handles_missing_and_errors():
    executor = PluginExecutor()
    ok_plugin = DummyPlugin()
    err_plugin = DummyPlugin(name="error.plugin")
    err_plugin.on_load = AsyncMock(side_effect=RuntimeError("boom"))

    def get_plugin(name):
        if name == ok_plugin.metadata.name:
            return ok_plugin
        if name == err_plugin.metadata.name:
            return err_plugin
        return None

    with patch("core.plugins.executor.registry.get", side_effect=get_plugin):
        await executor.warm_plugins(
            [ok_plugin.metadata.name, "missing.plugin", err_plugin.metadata.name]
        )
