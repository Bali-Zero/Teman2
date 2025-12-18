"""
Integration Tests for PluginRegistry
Tests plugin registration, discovery, and lifecycle with real plugins
"""

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestPluginRegistryIntegration:
    """Comprehensive integration tests for PluginRegistry"""

    @pytest_asyncio.fixture
    async def registry(self):
        """Create PluginRegistry instance"""
        from core.plugins.registry import PluginRegistry

        return PluginRegistry()

    @pytest_asyncio.fixture
    async def mock_plugin_class(self):
        """Create mock plugin class"""
        from core.plugins.plugin import Plugin, PluginCategory, PluginMetadata

        class TestPlugin(Plugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test.plugin",
                    version="1.0.0",
                    description="Test plugin",
                    category=PluginCategory.BALI_ZERO,
                )

            @property
            def input_schema(self):
                from pydantic import BaseModel

                class TestInput(BaseModel):
                    test_field: str

                return TestInput

            @property
            def output_schema(self):
                from pydantic import BaseModel

                class TestOutput(BaseModel):
                    result: str

                return TestOutput

            async def execute(self, input_data):
                return self.output_schema(result="test result")

            async def on_load(self):
                pass

            async def on_unload(self):
                pass

        return TestPlugin

    @pytest.mark.asyncio
    async def test_initialization(self, registry):
        """Test registry initialization"""
        assert registry is not None
        assert registry._plugins == {}
        assert registry._metadata == {}

    @pytest.mark.asyncio
    async def test_register_plugin(self, registry, mock_plugin_class):
        """Test registering a plugin"""
        plugin = await registry.register(mock_plugin_class)

        assert plugin is not None
        assert "test.plugin" in registry._plugins
        assert registry.get("test.plugin") == plugin

    @pytest.mark.asyncio
    async def test_register_plugin_duplicate(self, registry, mock_plugin_class):
        """Test registering duplicate plugin (same version)"""
        plugin1 = await registry.register(mock_plugin_class)
        plugin2 = await registry.register(mock_plugin_class)

        # Should return existing plugin
        assert plugin1 == plugin2

    @pytest.mark.asyncio
    async def test_register_batch(self, registry, mock_plugin_class):
        """Test registering multiple plugins in batch"""
        plugins = await registry.register_batch([mock_plugin_class])

        assert len(plugins) == 1
        assert plugins[0] is not None

    @pytest.mark.asyncio
    async def test_unregister_plugin(self, registry, mock_plugin_class):
        """Test unregistering a plugin"""
        await registry.register(mock_plugin_class)

        await registry.unregister("test.plugin")

        assert "test.plugin" not in registry._plugins

    @pytest.mark.asyncio
    async def test_get_plugin(self, registry, mock_plugin_class):
        """Test getting a plugin"""
        await registry.register(mock_plugin_class)

        plugin = registry.get("test.plugin")

        assert plugin is not None
        assert plugin.metadata.name == "test.plugin"

    @pytest.mark.asyncio
    async def test_get_plugin_not_found(self, registry):
        """Test getting non-existent plugin"""
        plugin = registry.get("nonexistent.plugin")

        assert plugin is None

    @pytest.mark.asyncio
    async def test_get_plugin_by_alias(self, registry, mock_plugin_class):
        """Test getting plugin by alias"""
        # Mock plugin with legacy handler key
        from core.plugins.plugin import PluginCategory, PluginMetadata

        mock_plugin_class.metadata = PropertyMock(
            return_value=PluginMetadata(
                name="test.plugin",
                version="1.0.0",
                description="Test",
                category=PluginCategory.BALI_ZERO,
                legacy_handler_key="test_handler",
            )
        )

        await registry.register(mock_plugin_class)

        plugin = registry.get("test_handler")

        assert plugin is not None

    def test_list_plugins_all(self, registry, mock_plugin_class):
        """Test listing all plugins"""
        import asyncio

        asyncio.run(registry.register(mock_plugin_class))

        plugins = registry.list_plugins()

        assert len(plugins) >= 1

    def test_list_plugins_by_category(self, registry, mock_plugin_class):
        """Test listing plugins by category"""
        import asyncio

        asyncio.run(registry.register(mock_plugin_class))

        from core.plugins.plugin import PluginCategory

        plugins = registry.list_plugins(category=PluginCategory.BALI_ZERO)

        assert len(plugins) >= 1

    def test_search_plugins(self, registry, mock_plugin_class):
        """Test searching plugins"""
        import asyncio

        asyncio.run(registry.register(mock_plugin_class))

        results = registry.search("test")

        assert len(results) >= 1

    def test_get_stats(self, registry, mock_plugin_class):
        """Test getting registry statistics"""
        import asyncio

        asyncio.run(registry.register(mock_plugin_class))

        stats = registry.get_stats()

        assert stats is not None
        assert "total_plugins" in stats
        assert stats["total_plugins"] >= 1

    @pytest.mark.asyncio
    async def test_plugin_lifecycle_hooks(self, registry, mock_plugin_class):
        """Test plugin lifecycle hooks (on_load, on_unload)"""
        plugin = await registry.register(mock_plugin_class)

        # on_load should have been called
        assert plugin is not None

        await registry.unregister("test.plugin")

        # on_unload should have been called
        assert "test.plugin" not in registry._plugins

    @pytest.mark.asyncio
    async def test_register_plugin_with_config(self, registry, mock_plugin_class):
        """Test registering plugin with configuration"""
        config = {"test_config": "test_value"}

        plugin = await registry.register(mock_plugin_class, config=config)

        assert plugin is not None
        # Plugin should have received config
        assert plugin.config == config

    def test_get_plugin_versions(self, registry, mock_plugin_class):
        """Test getting plugin versions"""
        import asyncio

        asyncio.run(registry.register(mock_plugin_class))

        versions = registry.get_versions("test.plugin")

        assert "1.0.0" in versions
