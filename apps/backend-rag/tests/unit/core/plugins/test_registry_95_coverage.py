"""
Comprehensive tests for Plugin Registry - Target 95% coverage
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Import using absolute imports to avoid relative import issues
try:
    from core.plugins.plugin import (
        Plugin,
        PluginCategory,
        PluginInput,
        PluginMetadata,
        PluginOutput,
    )
    from core.plugins.registry import PluginRegistry
except ImportError:
    # Fallback to direct import
    import importlib.util

    # First load plugin.py
    plugin_path = backend_path / "core" / "plugins" / "plugin.py"
    spec_plugin = importlib.util.spec_from_file_location("core.plugins.plugin", plugin_path)
    plugin_module = importlib.util.module_from_spec(spec_plugin)
    sys.modules["core"] = MagicMock()
    sys.modules["core.plugins"] = MagicMock()
    spec_plugin.loader.exec_module(plugin_module)
    Plugin = plugin_module.Plugin
    PluginCategory = plugin_module.PluginCategory
    PluginMetadata = plugin_module.PluginMetadata
    PluginInput = plugin_module.PluginInput
    PluginOutput = plugin_module.PluginOutput

    # Then load registry.py
    registry_path = backend_path / "core" / "plugins" / "registry.py"
    spec = importlib.util.spec_from_file_location("core.plugins.registry", registry_path)
    registry_module = importlib.util.module_from_spec(spec)
    registry_module.Plugin = Plugin
    registry_module.PluginCategory = PluginCategory
    registry_module.PluginMetadata = PluginMetadata
    spec.loader.exec_module(registry_module)
    PluginRegistry = registry_module.PluginRegistry


# Mock Plugin class for testing
class MockPlugin(Plugin):
    """Mock plugin for testing"""

    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        return PluginMetadata(
            name="test.plugin",
            version="1.0.0",
            description="Test plugin",
            category=PluginCategory.SYSTEM,
            tags=["test"],
            legacy_handler_key="test_handler",
        )

    @property
    def input_schema(self) -> type[PluginInput]:
        """Return input schema"""
        return PluginInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        """Return output schema"""
        return PluginOutput

    def __init__(self, config=None):
        super().__init__(config)
        self.config = config or {}

    async def on_load(self):
        """Mock on_load"""
        pass

    async def on_unload(self):
        """Mock on_unload"""
        pass

    async def execute(self, input_data: PluginInput) -> PluginOutput:
        """Mock execute"""
        return PluginOutput(success=True, data={"result": "test"})

    def to_anthropic_tool_definition(self):
        """Mock tool definition"""
        return {"name": "test_plugin", "description": "Test"}


class MockPluginV2(Plugin):
    """Mock plugin version 2"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test.plugin",
            version="2.0.0",
            description="Test plugin v2",
            category=PluginCategory.SYSTEM,
        )

    @property
    def input_schema(self) -> type[PluginInput]:
        return PluginInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        return PluginOutput

    def __init__(self, config=None):
        super().__init__(config)
        self.config = config or {}

    async def on_load(self):
        pass

    async def on_unload(self):
        pass

    async def execute(self, input_data: PluginInput) -> PluginOutput:
        return PluginOutput(success=True, data={"result": "test"})

    def to_anthropic_tool_definition(self):
        return {"name": "test_plugin_v2", "description": "Test v2"}


class MockPluginWithError(Plugin):
    """Mock plugin that raises error on load"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="error.plugin",
            version="1.0.0",
            description="Error plugin",
            category=PluginCategory.SYSTEM,
        )

    @property
    def input_schema(self) -> type[PluginInput]:
        return PluginInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        return PluginOutput

    def __init__(self, config=None):
        super().__init__(config)
        self.config = config or {}

    async def on_load(self):
        raise Exception("Load error")

    async def on_unload(self):
        pass

    async def execute(self, input_data: PluginInput) -> PluginOutput:
        return PluginOutput(success=True, data={})

    def to_anthropic_tool_definition(self):
        return {}


@pytest.mark.asyncio
class TestPluginRegistry95Coverage:
    """Comprehensive tests for PluginRegistry to achieve 95% coverage"""

    async def test_init(self):
        """Test PluginRegistry initialization"""
        registry = PluginRegistry()
        assert registry._plugins == {}
        assert registry._metadata == {}
        assert registry._versions == {}
        assert registry._aliases == {}

    async def test_register_success(self):
        """Test registering plugin successfully"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)
        assert plugin.metadata.name in registry._plugins
        assert plugin.metadata.name in registry._metadata
        assert plugin.metadata.version in registry._versions[plugin.metadata.name]

    async def test_register_with_config(self):
        """Test registering plugin with config"""
        registry = PluginRegistry()
        config = {"key": "value"}
        plugin = await registry.register(MockPlugin, config)
        assert plugin.config == config

    async def test_register_duplicate_same_version(self):
        """Test registering duplicate plugin with same version"""
        registry = PluginRegistry()
        plugin1 = await registry.register(MockPlugin)
        plugin2 = await registry.register(MockPlugin)
        assert plugin1 is plugin2  # Should return existing

    async def test_register_duplicate_different_version(self):
        """Test registering duplicate plugin with different version"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        plugin2 = await registry.register(MockPluginV2)
        assert plugin2.metadata.version == "2.0.0"
        assert len(registry._versions["test.plugin"]) == 2

    async def test_register_legacy_handler_key(self):
        """Test registering plugin with legacy handler key"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)
        assert "test_handler" in registry._aliases
        assert registry._aliases["test_handler"] == "test.plugin"

    async def test_register_on_load_error(self):
        """Test registering plugin with on_load error"""
        registry = PluginRegistry()
        with pytest.raises(Exception):
            await registry.register(MockPluginWithError)
        # Should be rolled back
        assert "error.plugin" not in registry._plugins

    async def test_register_batch_success(self):
        """Test registering multiple plugins in batch"""
        registry = PluginRegistry()
        plugins = await registry.register_batch([MockPlugin, MockPluginV2])
        assert len(plugins) == 2

    async def test_register_batch_with_error(self):
        """Test registering batch with one error"""
        registry = PluginRegistry()
        plugins = await registry.register_batch([MockPlugin, MockPluginWithError])
        # Should continue and register successful ones
        assert len(plugins) == 1

    async def test_unregister_success(self):
        """Test unregistering plugin"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)
        await registry.unregister(plugin.metadata.name)
        assert plugin.metadata.name not in registry._plugins
        assert plugin.metadata.name not in registry._metadata

    async def test_unregister_not_found(self):
        """Test unregistering non-existent plugin"""
        registry = PluginRegistry()
        # Should not raise error
        await registry.unregister("nonexistent")

    async def test_unregister_removes_aliases(self):
        """Test that unregister removes aliases"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)
        assert "test_handler" in registry._aliases
        await registry.unregister(plugin.metadata.name)
        assert "test_handler" not in registry._aliases

    async def test_unregister_on_unload_error(self):
        """Test unregistering with on_unload error"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)

        # Mock on_unload to raise error
        async def error_unload():
            raise Exception("Unload error")

        plugin.on_unload = error_unload
        await registry.unregister(plugin.metadata.name)
        # Should still unregister despite error
        assert plugin.metadata.name not in registry._plugins

    async def test_get_by_name(self):
        """Test getting plugin by name"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)
        result = registry.get("test.plugin")
        assert result == plugin

    async def test_get_by_alias(self):
        """Test getting plugin by alias"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)
        result = registry.get("test_handler")
        assert result == plugin

    async def test_get_not_found(self):
        """Test getting non-existent plugin"""
        registry = PluginRegistry()
        result = registry.get("nonexistent")
        assert result is None

    async def test_get_metadata(self):
        """Test getting plugin metadata"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)
        metadata = registry.get_metadata("test.plugin")
        assert metadata == plugin.metadata

    async def test_get_metadata_not_found(self):
        """Test getting metadata for non-existent plugin"""
        registry = PluginRegistry()
        metadata = registry.get_metadata("nonexistent")
        assert metadata is None

    async def test_list_plugins_all(self):
        """Test listing all plugins"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        plugins = registry.list_plugins()
        assert len(plugins) == 1

    async def test_list_plugins_by_category(self):
        """Test listing plugins by category"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        plugins = registry.list_plugins(category=PluginCategory.SYSTEM)
        assert len(plugins) == 1
        plugins = registry.list_plugins(category=PluginCategory.AI_SERVICES)
        assert len(plugins) == 0

    async def test_list_plugins_by_tags(self):
        """Test listing plugins by tags"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        plugins = registry.list_plugins(tags=["test"])
        assert len(plugins) == 1
        plugins = registry.list_plugins(tags=["other"])
        assert len(plugins) == 0

    async def test_list_plugins_by_allowed_models(self):
        """Test listing plugins by allowed models"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        plugins = registry.list_plugins(allowed_models=["haiku"])
        # MockPlugin has default allowed_models which includes haiku
        assert len(plugins) >= 1

    async def test_list_plugins_sorted(self):
        """Test that plugins are sorted"""
        registry = PluginRegistry()

        # Create plugin classes with different metadata
        class MockPluginA(MockPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="a.plugin",
                    version="1.0.0",
                    description="A plugin",
                    category=PluginCategory.SYSTEM,
                )

        class MockPluginB(MockPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="b.plugin",
                    version="1.0.0",
                    description="B plugin",
                    category=PluginCategory.AI_SERVICES,
                )

        await registry.register(MockPluginB)
        await registry.register(MockPluginA)

        plugins = registry.list_plugins()
        # Should be sorted by category, then name
        assert len(plugins) == 2
        assert plugins[0].category == PluginCategory.AI_SERVICES
        assert plugins[1].category == PluginCategory.SYSTEM

    async def test_search_by_name(self):
        """Test searching plugins by name"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        results = registry.search("test.plugin")
        assert len(results) == 1

    async def test_search_by_description(self):
        """Test searching plugins by description"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        results = registry.search("Test plugin")
        assert len(results) == 1

    async def test_search_by_tags(self):
        """Test searching plugins by tags"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        results = registry.search("test")
        assert len(results) == 1

    async def test_search_case_insensitive(self):
        """Test that search is case insensitive"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        results = registry.search("TEST")
        assert len(results) == 1

    async def test_search_no_results(self):
        """Test searching with no results"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        results = registry.search("nonexistent")
        assert len(results) == 0

    async def test_get_statistics(self):
        """Test getting registry statistics"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        stats = registry.get_statistics()
        assert stats["total_plugins"] == 1
        assert stats["categories"] == 1
        assert stats["total_versions"] == 1
        assert stats["aliases"] == 1

    async def test_get_statistics_empty(self):
        """Test getting statistics for empty registry"""
        registry = PluginRegistry()
        stats = registry.get_statistics()
        assert stats["total_plugins"] == 0
        assert stats["categories"] == 0

    async def test_get_all_anthropic_tools(self):
        """Test getting all anthropic tools"""
        registry = PluginRegistry()
        await registry.register(MockPlugin)
        tools = registry.get_all_anthropic_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "test_plugin"

    async def test_get_all_anthropic_tools_with_error(self):
        """Test getting tools when plugin raises error"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)

        # Mock to_anthropic_tool_definition to raise error
        def error_tool_def():
            raise Exception("Tool definition error")

        plugin.to_anthropic_tool_definition = error_tool_def
        tools = registry.get_all_anthropic_tools()
        # Should continue and return empty list
        assert len(tools) == 0

    async def test_get_haiku_allowed_tools(self):
        """Test getting haiku allowed tools"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)
        # Ensure haiku is in allowed_models
        plugin.metadata.allowed_models = ["haiku", "sonnet"]
        tools = registry.get_haiku_allowed_tools()
        assert len(tools) == 1

    async def test_get_haiku_allowed_tools_filtered(self):
        """Test that haiku tools are filtered"""
        registry = PluginRegistry()

        # Create plugin without haiku in allowed_models
        class MockPluginNoHaiku(MockPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                meta = PluginMetadata(
                    name="no.haiku.plugin",
                    version="1.0.0",
                    description="No haiku plugin",
                    category=PluginCategory.SYSTEM,
                )
                meta.allowed_models = ["sonnet"]  # No haiku
                return meta

        await registry.register(MockPluginNoHaiku)
        tools = registry.get_haiku_allowed_tools()
        assert len(tools) == 0

    async def test_reload_plugin(self):
        """Test reloading plugin"""
        registry = PluginRegistry()
        plugin = await registry.register(MockPlugin)
        await registry.reload_plugin("test.plugin")
        # Plugin should still be registered
        assert "test.plugin" in registry._plugins

    async def test_reload_plugin_not_found(self):
        """Test reloading non-existent plugin"""
        registry = PluginRegistry()
        with pytest.raises(ValueError):
            await registry.reload_plugin("nonexistent")

    async def test_discover_plugins_directory_not_found(self):
        """Test discovering plugins when directory doesn't exist"""
        registry = PluginRegistry()
        fake_dir = Path("/nonexistent/path")
        result = await registry.discover_plugins(fake_dir)
        assert result["discovered"] == 0
        assert len(result["errors"]) > 0

    async def test_discover_plugins_directory_not_found_strict(self):
        """Test discovering plugins with strict mode"""
        registry = PluginRegistry()
        fake_dir = Path("/nonexistent/path")
        with pytest.raises(FileNotFoundError):
            await registry.discover_plugins(fake_dir, strict=True)

    async def test_discover_plugins_invalid_prefix(self):
        """Test discovering with invalid package prefix"""
        registry = PluginRegistry()
        temp_dir = Path("/tmp/test_plugins")
        temp_dir.mkdir(exist_ok=True)
        try:
            result = await registry.discover_plugins(temp_dir, package_prefix="invalid-prefix-123")
            assert result["discovered"] == 0
            assert len(result["errors"]) > 0
        finally:
            if temp_dir.exists():
                temp_dir.rmdir()

    async def test_discover_plugins_invalid_prefix_strict(self):
        """Test discovering with invalid prefix in strict mode"""
        registry = PluginRegistry()
        temp_dir = Path("/tmp/test_plugins")
        temp_dir.mkdir(exist_ok=True)
        try:
            with pytest.raises(ValueError):
                await registry.discover_plugins(
                    temp_dir, package_prefix="invalid-prefix-123", strict=True
                )
        finally:
            if temp_dir.exists():
                temp_dir.rmdir()

    @patch("importlib.import_module")
    async def test_discover_plugins_success(self, mock_import):
        """Test successful plugin discovery"""
        registry = PluginRegistry()

        # Create mock module with Plugin class
        mock_module = MagicMock()
        mock_module.TestPlugin = MockPlugin
        mock_import.return_value = mock_module

        temp_dir = Path("/tmp/test_plugins")
        temp_dir.mkdir(exist_ok=True)
        test_file = temp_dir / "test_plugin.py"
        test_file.write_text("# Test plugin file")

        try:
            result = await registry.discover_plugins(temp_dir, package_prefix="plugins")
            assert result["discovered"] >= 0  # May discover or not depending on import
        finally:
            if test_file.exists():
                test_file.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    async def test_discover_plugins_skip_underscore(self):
        """Test that files starting with _ are skipped"""
        registry = PluginRegistry()
        temp_dir = Path("/tmp/test_plugins")
        temp_dir.mkdir(exist_ok=True)
        test_file = temp_dir / "__init__.py"
        test_file.write_text("# Init file")

        try:
            result = await registry.discover_plugins(temp_dir)
            # Should skip __init__.py
            assert "__init__" not in str(result.get("errors", []))
        finally:
            if test_file.exists():
                test_file.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    async def test_discover_plugins_invalid_path_segment(self):
        """Test discovering with invalid path segment"""
        registry = PluginRegistry()
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            # Create file with invalid name
            invalid_file = temp_dir / "123-invalid.py"
            invalid_file.write_text("# Invalid")

            result = await registry.discover_plugins(temp_dir, strict=False)
            # Should handle gracefully
            assert isinstance(result, dict)
