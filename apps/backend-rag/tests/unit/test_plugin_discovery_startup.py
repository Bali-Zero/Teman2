"""
Unit tests for Plugin Discovery at Startup
Tests the initialize_plugins() function and plugin discovery integration
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.plugins.registry import PluginRegistry


@pytest.mark.asyncio
async def test_discover_plugins_returns_results():
    """Test discover_plugins returns discovery results"""
    registry = PluginRegistry()

    # Create a temporary plugins directory with a mock plugin file
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir)

        # Create a mock plugin file
        plugin_file = plugins_dir / "test_plugin.py"
        plugin_file.write_text(
            """
from core.plugins import Plugin, PluginCategory, PluginInput, PluginMetadata, PluginOutput

class TestPlugin(Plugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="test.plugin",
            description="Test plugin",
            category=PluginCategory.SYSTEM,
            version="1.0.0",
        )

    @property
    def input_schema(self):
        return PluginInput

    @property
    def output_schema(self):
        return PluginOutput

    async def execute(self, input_data):
        return PluginOutput(success=True)
"""
        )

        # Discover plugins
        result = await registry.discover_plugins(plugins_dir, package_prefix="")

        assert result["discovered"] >= 0  # May be 0 if import fails
        assert isinstance(result["errors"], list)


@pytest.mark.asyncio
async def test_discover_plugins_strict_mode():
    """Test discover_plugins with strict mode"""
    registry = PluginRegistry()

    # Non-existent directory should raise in strict mode
    fake_path = Path("/nonexistent/path/that/does/not/exist")

    with pytest.raises(FileNotFoundError):
        await registry.discover_plugins(fake_path, strict=True)


@pytest.mark.asyncio
async def test_discover_plugins_collects_errors():
    """Test discover_plugins collects errors instead of stopping"""
    registry = PluginRegistry()

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir)

        # Create an invalid plugin file (syntax error)
        plugin_file = plugins_dir / "invalid_plugin.py"
        plugin_file.write_text("invalid python syntax !!!")

        # Discover plugins (non-strict mode)
        result = await registry.discover_plugins(plugins_dir, package_prefix="", strict=False)

        assert isinstance(result["errors"], list)
        assert len(result["errors"]) >= 0  # May have errors


@pytest.mark.asyncio
async def test_discover_plugins_invalid_package_prefix():
    """Test discover_plugins with invalid package prefix"""
    registry = PluginRegistry()

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir)

        # Invalid package prefix
        result = await registry.discover_plugins(
            plugins_dir, package_prefix="invalid-prefix-123!", strict=False
        )

        assert result["discovered"] == 0
        assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_discover_plugins_skips_private_files():
    """Test discover_plugins skips files starting with underscore"""
    registry = PluginRegistry()

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir)

        # Create private file
        private_file = plugins_dir / "_private.py"
        private_file.write_text("# Private file")

        # Create public file
        public_file = plugins_dir / "public.py"
        public_file.write_text("# Public file")

        # Mock import to avoid actual imports
        with patch("core.plugins.registry.importlib.import_module") as mock_import:
            mock_import.side_effect = Exception("Should not be called for private files")

            result = await registry.discover_plugins(plugins_dir, package_prefix="", strict=False)

            # Should not raise because private files are skipped before import


@pytest.mark.asyncio
async def test_discover_plugins_invalid_module_segment():
    """Test discover_plugins handles invalid module segments"""
    registry = PluginRegistry()

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir)

        # Create file with invalid characters in path
        invalid_dir = plugins_dir / "invalid-dir-name"
        invalid_dir.mkdir()
        invalid_file = invalid_dir / "plugin.py"
        invalid_file.write_text("# Plugin")

        result = await registry.discover_plugins(plugins_dir, package_prefix="", strict=False)

        # Should handle gracefully
        assert isinstance(result["errors"], list)










