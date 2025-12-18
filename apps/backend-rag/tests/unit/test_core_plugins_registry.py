"""
Unit tests for Plugin Registry
Coverage target: 90%+ (151 statements)
Tests registration, discovery, lifecycle, search, and statistics
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.plugins.plugin import Plugin, PluginCategory, PluginInput, PluginMetadata, PluginOutput
from core.plugins.registry import PluginRegistry

# ============================================================================
# Mock Plugins
# ============================================================================


class MockPlugin(Plugin):
    def __init__(self, config=None):
        super().__init__(config)

    @property
    def metadata(self):
        return PluginMetadata(
            name="test.plugin",
            description="Test plugin for unit tests",
            category=PluginCategory.SYSTEM,
            version="1.0.0",
            allowed_models=["opus"],
        )

    @property
    def input_schema(self):
        return PluginInput

    @property
    def output_schema(self):
        return PluginOutput

    async def execute(self, input_data):
        return PluginOutput(success=True, data={"result": "test"})


class MockPluginV2(Plugin):
    def __init__(self, config=None):
        super().__init__(config)

    @property
    def metadata(self):
        return PluginMetadata(
            name="test.plugin",
            description="Test plugin v2",
            category=PluginCategory.SYSTEM,
            version="2.0.0",
        )

    @property
    def input_schema(self):
        return PluginInput

    @property
    def output_schema(self):
        return PluginOutput

    async def execute(self, input_data):
        return PluginOutput(success=True, data={"result": "v2"})


class ToolsPlugin(Plugin):
    def __init__(self, config=None):
        super().__init__(config)

    @property
    def metadata(self):
        return PluginMetadata(
            name="tools.plugin",
            description="Tools category plugin",
            category=PluginCategory.ANALYTICS,
            version="1.0.0",
            tags=["analytics", "tools"],
            allowed_models=["haiku", "sonnet"],
        )

    @property
    def input_schema(self):
        return PluginInput

    @property
    def output_schema(self):
        return PluginOutput

    async def execute(self, input_data):
        return PluginOutput(success=True)


class LegacyPlugin(Plugin):
    def __init__(self, config=None):
        super().__init__(config)

    @property
    def metadata(self):
        return PluginMetadata(
            name="new.plugin",
            description="Plugin with legacy key",
            category=PluginCategory.BUSINESS,
            version="1.0.0",
            legacy_handler_key="old.handler",
        )

    @property
    def input_schema(self):
        return PluginInput

    @property
    def output_schema(self):
        return PluginOutput

    async def execute(self, input_data):
        return PluginOutput(success=True)


class FailLoadPlugin(Plugin):
    def __init__(self, config=None):
        super().__init__(config)

    @property
    def metadata(self):
        return PluginMetadata(
            name="fail.plugin",
            description="Fails on load",
            category=PluginCategory.SYSTEM,
            version="1.0.0",
        )

    @property
    def input_schema(self):
        return PluginInput

    @property
    def output_schema(self):
        return PluginOutput

    async def on_load(self):
        raise Exception("Load failed")

    async def execute(self, input_data):
        return PluginOutput(success=True)


class UnloadPlugin(Plugin):
    def __init__(self, config=None):
        super().__init__(config)

    @property
    def metadata(self):
        return PluginMetadata(
            name="unload.plugin",
            description="Test unload",
            category=PluginCategory.SYSTEM,
            version="1.0.0",
        )

    @property
    def input_schema(self):
        return PluginInput

    @property
    def output_schema(self):
        return PluginOutput

    async def on_unload(self):
        pass

    async def execute(self, input_data):
        return PluginOutput(success=True)


class UnloadErrorPlugin(Plugin):
    def __init__(self, config=None):
        super().__init__(config)

    @property
    def metadata(self):
        return PluginMetadata(
            name="unload.error.plugin",
            description="Test unload error",
            category=PluginCategory.SYSTEM,
            version="1.0.0",
        )

    @property
    def input_schema(self):
        return PluginInput

    @property
    def output_schema(self):
        return PluginOutput

    async def on_unload(self):
        raise Exception("Unload failed")

    async def execute(self, input_data):
        return PluginOutput(success=True)


class ToolDefErrorPlugin(Plugin):
    def __init__(self, config=None):
        super().__init__(config)

    @property
    def metadata(self):
        return PluginMetadata(
            name="tooldef.error.plugin",
            description="Test tool definition error",
            category=PluginCategory.SYSTEM,
            version="1.0.0",
            allowed_models=["haiku"],
        )

    @property
    def input_schema(self):
        return PluginInput

    @property
    def output_schema(self):
        return PluginOutput

    def to_anthropic_tool_definition(self):
        raise Exception("Tool definition failed")

    async def execute(self, input_data):
        return PluginOutput(success=True)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def registry():
    """Fresh registry instance"""
    reg = PluginRegistry()
    reg._plugins = {}
    reg._metadata = {}
    reg._versions = {}
    reg._aliases = {}
    return reg


# ============================================================================
# Test Registration
# ============================================================================


@pytest.mark.asyncio
async def test_register_plugin(registry):
    """Test basic plugin registration"""
    plugin = await registry.register(MockPlugin)

    assert plugin is not None
    assert "test.plugin" in registry._plugins
    assert registry._plugins["test.plugin"] == plugin
    assert "test.plugin" in registry._metadata


@pytest.mark.asyncio
async def test_register_with_config(registry):
    """Test registering plugin with config"""
    config = {"key": "value"}
    plugin = await registry.register(MockPlugin, config)

    assert plugin.config == config


@pytest.mark.asyncio
async def test_register_duplicate_same_version(registry):
    """Test registering duplicate plugin with same version"""
    plugin1 = await registry.register(MockPlugin)
    plugin2 = await registry.register(MockPlugin)

    # Should return existing plugin
    assert plugin1 == plugin2


@pytest.mark.asyncio
async def test_register_duplicate_different_version(registry):
    """Test registering plugin with different version"""
    await registry.register(MockPlugin)
    plugin_v2 = await registry.register(MockPluginV2)

    # Should register new version
    assert "test.plugin" in registry._plugins
    assert registry._plugins["test.plugin"].metadata.version == "2.0.0"


@pytest.mark.asyncio
async def test_register_tracks_versions(registry):
    """Test version tracking"""
    await registry.register(MockPlugin)
    await registry.register(MockPluginV2)

    assert "test.plugin" in registry._versions
    assert "1.0.0" in registry._versions["test.plugin"]
    assert "2.0.0" in registry._versions["test.plugin"]


@pytest.mark.asyncio
async def test_register_legacy_alias(registry):
    """Test legacy handler key creates alias"""
    await registry.register(LegacyPlugin)

    assert "old.handler" in registry._aliases
    assert registry._aliases["old.handler"] == "new.plugin"


@pytest.mark.asyncio
async def test_register_fail_on_load(registry):
    """Test registration rollback on load failure"""
    with pytest.raises(Exception, match="Load failed"):
        await registry.register(FailLoadPlugin)

    # Should not be registered
    assert "fail.plugin" not in registry._plugins
    assert "fail.plugin" not in registry._metadata


@pytest.mark.asyncio
async def test_register_batch(registry):
    """Test batch registration"""
    plugins = await registry.register_batch([MockPlugin, ToolsPlugin])

    assert len(plugins) == 2
    assert "test.plugin" in registry._plugins
    assert "tools.plugin" in registry._plugins


@pytest.mark.asyncio
async def test_register_batch_with_failure(registry):
    """Test batch registration continues on failure"""
    plugins = await registry.register_batch([MockPlugin, FailLoadPlugin, ToolsPlugin])

    # Should have 2 plugins (failing one skipped)
    assert len(plugins) == 2
    assert "test.plugin" in registry._plugins
    assert "tools.plugin" in registry._plugins
    assert "fail.plugin" not in registry._plugins


# ============================================================================
# Test Unregistration
# ============================================================================


@pytest.mark.asyncio
async def test_unregister_plugin(registry):
    """Test unregistering plugin"""
    await registry.register(UnloadPlugin)
    assert "unload.plugin" in registry._plugins

    await registry.unregister("unload.plugin")

    assert "unload.plugin" not in registry._plugins
    assert "unload.plugin" not in registry._metadata


@pytest.mark.asyncio
async def test_unregister_removes_aliases(registry):
    """Test unregistering removes aliases"""
    await registry.register(LegacyPlugin)
    assert "old.handler" in registry._aliases

    await registry.unregister("new.plugin")

    assert "old.handler" not in registry._aliases


@pytest.mark.asyncio
async def test_unregister_nonexistent(registry):
    """Test unregistering non-existent plugin"""
    # Should not raise
    await registry.unregister("nonexistent.plugin")


# ============================================================================
# Test Retrieval
# ============================================================================


@pytest.mark.asyncio
async def test_get_plugin(registry):
    """Test getting plugin by name"""
    plugin = await registry.register(MockPlugin)
    retrieved = registry.get("test.plugin")

    assert retrieved == plugin


@pytest.mark.asyncio
async def test_get_by_alias(registry):
    """Test getting plugin by legacy alias"""
    plugin = await registry.register(LegacyPlugin)
    retrieved = registry.get("old.handler")

    assert retrieved == plugin


@pytest.mark.asyncio
async def test_get_nonexistent(registry):
    """Test getting non-existent plugin"""
    result = registry.get("nonexistent.plugin")

    assert result is None


@pytest.mark.asyncio
async def test_get_metadata(registry):
    """Test getting plugin metadata"""
    await registry.register(MockPlugin)
    metadata = registry.get_metadata("test.plugin")

    assert metadata is not None
    assert metadata.name == "test.plugin"
    assert metadata.version == "1.0.0"


@pytest.mark.asyncio
async def test_get_metadata_nonexistent(registry):
    """Test getting metadata for non-existent plugin"""
    result = registry.get_metadata("nonexistent.plugin")

    assert result is None


# ============================================================================
# Test Listing & Filtering
# ============================================================================


@pytest.mark.asyncio
async def test_list_all_plugins(registry):
    """Test listing all plugins"""
    await registry.register(MockPlugin)
    await registry.register(ToolsPlugin)

    plugins = registry.list_plugins()

    assert len(plugins) == 2


@pytest.mark.asyncio
async def test_list_by_category(registry):
    """Test listing plugins by category"""
    await registry.register(MockPlugin)  # SYSTEM
    await registry.register(ToolsPlugin)  # ANALYTICS

    system_plugins = registry.list_plugins(category=PluginCategory.SYSTEM)
    analytics_plugins = registry.list_plugins(category=PluginCategory.ANALYTICS)

    assert len(system_plugins) == 1
    assert len(analytics_plugins) == 1
    assert system_plugins[0].name == "test.plugin"
    assert analytics_plugins[0].name == "tools.plugin"


@pytest.mark.asyncio
async def test_list_by_tags(registry):
    """Test listing plugins by tags"""
    await registry.register(MockPlugin)
    await registry.register(ToolsPlugin)

    tagged = registry.list_plugins(tags=["tools"])

    assert len(tagged) == 1
    assert tagged[0].name == "tools.plugin"


@pytest.mark.asyncio
async def test_list_by_allowed_models(registry):
    """Test listing plugins by allowed models"""
    await registry.register(MockPlugin)
    await registry.register(ToolsPlugin)

    haiku_plugins = registry.list_plugins(allowed_models=["haiku"])

    assert len(haiku_plugins) == 1
    assert haiku_plugins[0].name == "tools.plugin"


@pytest.mark.asyncio
async def test_list_multiple_filters(registry):
    """Test listing with multiple filters"""
    await registry.register(ToolsPlugin)

    results = registry.list_plugins(
        category=PluginCategory.ANALYTICS, tags=["tools"], allowed_models=["haiku"]
    )

    assert len(results) == 1
    assert results[0].name == "tools.plugin"


# ============================================================================
# Test Search
# ============================================================================


@pytest.mark.asyncio
async def test_search_by_name(registry):
    """Test searching plugins by name"""
    await registry.register(MockPlugin)
    await registry.register(ToolsPlugin)

    results = registry.search("test")

    assert len(results) == 1
    assert results[0].name == "test.plugin"


@pytest.mark.asyncio
async def test_search_by_description(registry):
    """Test searching by description"""
    await registry.register(ToolsPlugin)

    results = registry.search("tools category")

    assert len(results) == 1
    assert results[0].name == "tools.plugin"


@pytest.mark.asyncio
async def test_search_by_tags(registry):
    """Test searching by tags"""
    await registry.register(ToolsPlugin)

    results = registry.search("tools")

    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_case_insensitive(registry):
    """Test search is case insensitive"""
    await registry.register(MockPlugin)

    results = registry.search("TEST")

    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_no_results(registry):
    """Test search with no results"""
    await registry.register(MockPlugin)

    results = registry.search("nonexistent")

    assert len(results) == 0


# ============================================================================
# Test Statistics
# ============================================================================


@pytest.mark.asyncio
async def test_statistics(registry):
    """Test getting registry statistics"""
    await registry.register(MockPlugin)
    await registry.register(ToolsPlugin)
    await registry.register(LegacyPlugin)

    stats = registry.get_statistics()

    assert stats["total_plugins"] == 3
    assert stats["categories"] == 3
    assert stats["aliases"] == 1
    assert PluginCategory.SYSTEM in stats["category_counts"]


@pytest.mark.asyncio
async def test_statistics_empty(registry):
    """Test statistics for empty registry"""
    stats = registry.get_statistics()

    assert stats["total_plugins"] == 0
    assert stats["categories"] == 0
    assert stats["aliases"] == 0


# ============================================================================
# Test Tool Definitions
# ============================================================================


@pytest.mark.asyncio
async def test_get_all_anthropic_tools(registry):
    """Test getting all tool definitions"""
    await registry.register(MockPlugin)
    await registry.register(ToolsPlugin)

    tools = registry.get_all_anthropic_tools()

    assert len(tools) == 2


@pytest.mark.asyncio
async def test_get_haiku_allowed_tools(registry):
    """Test getting Haiku-allowed tools"""
    await registry.register(MockPlugin)
    await registry.register(ToolsPlugin)

    tools = registry.get_haiku_allowed_tools()

    # Only ToolsPlugin has haiku in allowed_models
    assert len(tools) == 1


# ============================================================================
# Test Plugin Discovery
# ============================================================================


@pytest.mark.asyncio
async def test_discover_plugins_directory_not_exists(registry):
    """Test discovering from non-existent directory"""
    fake_path = Path("/nonexistent/path")

    # Should not raise
    await registry.discover_plugins(fake_path)


@pytest.mark.asyncio
async def test_discover_plugins(registry):
    """Test plugin discovery"""
    mock_dir = MagicMock()
    mock_dir.exists.return_value = True
    mock_dir.rglob.return_value = []

    await registry.discover_plugins(mock_dir)

    mock_dir.rglob.assert_called_once_with("*.py")


@pytest.mark.asyncio
async def test_discover_plugins_with_files(registry):
    """Test discovering plugins from files"""
    # Create mock directory
    mock_dir = MagicMock()
    mock_dir.exists.return_value = True

    # Create mock plugin files
    mock_file1 = MagicMock()
    mock_file1.name = "test_plugin.py"
    mock_file1.relative_to.return_value = Path("test_plugin.py")
    mock_file1.with_suffix.return_value = Path("test_plugin")

    mock_file2 = MagicMock()
    mock_file2.name = "_private.py"  # Should be skipped

    mock_file3 = MagicMock()
    mock_file3.name = "invalid.py"  # Will cause import error
    mock_file3.relative_to.return_value = Path("invalid.py")
    mock_file3.with_suffix.return_value = Path("invalid")

    mock_dir.rglob.return_value = [mock_file1, mock_file2, mock_file3]

    # Mock importlib to avoid actual imports
    with patch("core.plugins.registry.importlib.import_module") as mock_import:
        with patch("core.plugins.registry.inspect.getmembers") as mock_getmembers:
            # First import succeeds but has no Plugin classes
            mock_module = MagicMock()
            mock_import.side_effect = [
                mock_module,  # test_plugin.py - no plugins
                Exception("Import failed"),  # invalid.py - import error
            ]
            mock_getmembers.return_value = []  # No Plugin classes found

            await registry.discover_plugins(mock_dir, package_prefix="test")

            # Should have been called at least once
            assert mock_import.call_count >= 1


@pytest.mark.asyncio
async def test_discover_plugins_registration_error(registry):
    """Test discovery handles plugin registration errors gracefully"""
    mock_dir = MagicMock()
    mock_dir.exists.return_value = True

    mock_file = MagicMock()
    mock_file.name = "fail_plugin.py"
    mock_file.relative_to.return_value = Path("fail_plugin.py")
    mock_file.with_suffix.return_value = Path("fail_plugin")

    mock_dir.rglob.return_value = [mock_file]

    with patch("core.plugins.registry.importlib.import_module") as mock_import:
        mock_module = MagicMock()
        mock_import.return_value = mock_module

        with patch("core.plugins.registry.inspect.getmembers") as mock_getmembers:
            # Return FailLoadPlugin which will fail on registration
            mock_getmembers.return_value = [("FailLoadPlugin", FailLoadPlugin), ("Plugin", Plugin)]

            await registry.discover_plugins(mock_dir)

            # Plugin should not be registered due to on_load failure
            assert "fail.plugin" not in registry._plugins


# ============================================================================
# Test Reload
# ============================================================================


@pytest.mark.asyncio
async def test_reload_plugin(registry):
    """Test reloading plugin"""
    plugin = await registry.register(MockPlugin, {"key": "value"})

    await registry.reload_plugin("test.plugin")

    # Should be reloaded
    reloaded = registry.get("test.plugin")
    assert reloaded is not None
    assert reloaded.config == {"key": "value"}


@pytest.mark.asyncio
async def test_reload_nonexistent_plugin(registry):
    """Test reloading non-existent plugin"""
    with pytest.raises(ValueError, match="not found"):
        await registry.reload_plugin("nonexistent.plugin")


# ============================================================================
# Test Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_unregister_with_unload_error(registry):
    """Test unregistering plugin when unload fails"""
    await registry.register(UnloadErrorPlugin)
    assert "unload.error.plugin" in registry._plugins

    # Should not raise even if unload fails
    await registry.unregister("unload.error.plugin")

    # Plugin should still be removed despite unload error
    assert "unload.error.plugin" not in registry._plugins


@pytest.mark.asyncio
async def test_get_all_anthropic_tools_with_error(registry):
    """Test getting tools when some plugins fail to generate definitions"""
    await registry.register(MockPlugin)
    await registry.register(ToolDefErrorPlugin)

    tools = registry.get_all_anthropic_tools()

    # Should return tools from successful plugins, skip failed ones
    assert len(tools) == 1
    assert tools[0]["name"] == "test_plugin"


@pytest.mark.asyncio
async def test_get_haiku_allowed_tools_with_error(registry):
    """Test getting Haiku tools when some plugins fail"""
    await registry.register(ToolsPlugin)
    await registry.register(ToolDefErrorPlugin)

    tools = registry.get_haiku_allowed_tools()

    # Should return tools from successful plugins only
    assert len(tools) == 1
    assert tools[0]["name"] == "tools_plugin"


# ============================================================================
# Test Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_registration(registry):
    """Test concurrent plugin registration with lock"""
    import asyncio

    async def register_plugin(plugin_class):
        return await registry.register(plugin_class)

    # Register multiple plugins concurrently
    results = await asyncio.gather(
        register_plugin(MockPlugin), register_plugin(ToolsPlugin), register_plugin(LegacyPlugin)
    )

    assert len(results) == 3
    assert len(registry._plugins) == 3


def test_registry_initialization():
    """Test registry initialization"""
    reg = PluginRegistry()

    assert len(reg._plugins) == 0
    assert len(reg._metadata) == 0
    assert len(reg._versions) == 0
    assert len(reg._aliases) == 0
    assert reg._lock is not None
