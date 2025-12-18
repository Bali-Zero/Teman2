"""
Unit tests for Plugin System
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.plugins.executor import PluginExecutor
from core.plugins.plugin import (
    Plugin,
    PluginCategory,
    PluginInput,
    PluginMetadata,
    PluginOutput,
)
from core.plugins.registry import PluginRegistry

# ============================================================================
# Test Plugin Implementation
# ============================================================================


class MockTestPlugin(Plugin):
    """Mock plugin implementation for testing"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test.plugin",
            description="Test plugin",
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
        return PluginOutput(success=True, data={"result": "test"})


# ============================================================================
# Tests for PluginMetadata
# ============================================================================


def test_plugin_metadata_creation():
    """Test creating plugin metadata"""
    metadata = PluginMetadata(
        name="test.plugin",
        description="Test description",
        category=PluginCategory.SYSTEM,
    )

    assert metadata.name == "test.plugin"
    assert metadata.description == "Test description"
    assert metadata.category == PluginCategory.SYSTEM
    assert metadata.version == "1.0.0"


def test_plugin_metadata_version_validation():
    """Test plugin metadata version validation"""
    with pytest.raises(ValueError, match="Version must be in format"):
        PluginMetadata(
            name="test",
            description="test",
            category=PluginCategory.SYSTEM,
            version="invalid",
        )


# ============================================================================
# Tests for Plugin
# ============================================================================


def test_plugin_initialization():
    """Test plugin initialization"""
    plugin = MockTestPlugin()
    assert plugin.config == {}
    assert plugin.metadata.name == "test.plugin"


def test_plugin_initialization_with_config():
    """Test plugin initialization with config"""
    config = {"key": "value"}
    plugin = MockTestPlugin(config=config)
    assert plugin.config == config


@pytest.mark.asyncio
async def test_plugin_execute():
    """Test plugin execution"""
    plugin = MockTestPlugin()
    input_data = PluginInput()
    result = await plugin.execute(input_data)

    assert result.success is True
    assert result.data == {"result": "test"}


@pytest.mark.asyncio
async def test_plugin_validate():
    """Test plugin validation"""
    plugin = MockTestPlugin()
    input_data = PluginInput()
    result = await plugin.validate(input_data)

    assert result is True


@pytest.mark.asyncio
async def test_plugin_lifecycle_hooks():
    """Test plugin lifecycle hooks"""
    plugin = MockTestPlugin()
    await plugin.on_load()
    await plugin.on_unload()


def test_plugin_to_anthropic_tool_definition():
    """Test plugin conversion to Anthropic tool definition"""
    plugin = MockTestPlugin()
    tool_def = plugin.to_anthropic_tool_definition()

    assert "name" in tool_def
    assert "description" in tool_def
    assert "input_schema" in tool_def


def test_plugin_to_handler_format():
    """Test plugin conversion to handler format"""
    plugin = MockTestPlugin()
    handler_format = plugin.to_handler_format()

    assert "key" in handler_format
    assert "description" in handler_format
    assert "tags" in handler_format


# ============================================================================
# Tests for PluginRegistry
# ============================================================================


@pytest.mark.asyncio
async def test_registry_register():
    """Test registering a plugin"""
    registry = PluginRegistry()
    plugin = await registry.register(MockTestPlugin)

    assert plugin is not None
    assert registry.get("test.plugin") == plugin


@pytest.mark.asyncio
async def test_registry_get():
    """Test getting a plugin from registry"""
    registry = PluginRegistry()
    await registry.register(MockTestPlugin)

    plugin = registry.get("test.plugin")
    assert plugin is not None
    assert isinstance(plugin, MockTestPlugin)


@pytest.mark.asyncio
async def test_registry_get_not_found():
    """Test getting non-existent plugin"""
    registry = PluginRegistry()
    plugin = registry.get("nonexistent.plugin")

    assert plugin is None


@pytest.mark.asyncio
async def test_registry_list_plugins():
    """Test listing plugins"""
    registry = PluginRegistry()
    await registry.register(MockTestPlugin)

    plugins = registry.list_plugins()
    assert len(plugins) == 1
    assert plugins[0].name == "test.plugin"  # list_plugins returns PluginMetadata objects


@pytest.mark.asyncio
async def test_registry_search():
    """Test searching plugins"""
    registry = PluginRegistry()
    await registry.register(MockTestPlugin)

    results = registry.search("test")
    assert len(results) == 1


# ============================================================================
# Tests for PluginExecutor
# ============================================================================


@pytest.mark.asyncio
async def test_executor_execute_success():
    """Test plugin executor execution"""
    executor = PluginExecutor()
    registry = MagicMock()
    plugin = MockTestPlugin()
    registry.get = MagicMock(return_value=plugin)

    with patch("core.plugins.executor.registry", registry):
        result = await executor.execute("test.plugin", {})

        assert result.success is True


@pytest.mark.asyncio
async def test_executor_execute_plugin_not_found():
    """Test executor with non-existent plugin"""
    executor = PluginExecutor()
    registry = MagicMock()
    registry.get = MagicMock(return_value=None)

    with patch("core.plugins.executor.registry", registry):
        result = await executor.execute("nonexistent.plugin", {})

        assert result.success is False
        assert "not found" in result.error


@pytest.mark.asyncio
async def test_executor_execute_with_cache():
    """Test executor with caching"""
    executor = PluginExecutor(redis_client=None)
    registry = MagicMock()
    plugin = MockTestPlugin()
    registry.get = MagicMock(return_value=plugin)

    with patch("core.plugins.executor.registry", registry):
        result1 = await executor.execute("test.plugin", {}, use_cache=True)
        result2 = await executor.execute("test.plugin", {}, use_cache=True)

        assert result1.success is True
        assert result2.success is True
