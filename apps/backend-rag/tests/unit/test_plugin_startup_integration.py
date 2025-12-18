"""
Integration tests for Plugin Discovery at Startup
Tests the initialize_plugins() function integration with FastAPI
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Mock environment variables and settings"""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", "{}")

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.database_url = "postgresql://user:pass@localhost:5432/db"
        mock_settings.google_api_key = "test_key"
        mock_settings.google_credentials_json = "{}"
        mock_settings.API_V1_STR = "/api/v1"
        mock_settings.PROJECT_NAME = "Test Project"
        mock_settings.log_level = "INFO"
        yield mock_settings


@pytest.mark.asyncio
async def test_initialize_plugins_success():
    """Test initialize_plugins successfully discovers plugins"""
    print("DEBUG: Running test_initialize_plugins_success with PATCHED code")
    if "app.main_cloud" in sys.modules:
        del sys.modules["app.main_cloud"]
    from app.main_cloud import initialize_plugins

    # Mock app state
    mock_app = MagicMock()
    mock_app.state = MagicMock()

    # Mock registry
    mock_registry = MagicMock()
    mock_registry.discover_plugins = AsyncMock(return_value={"discovered": 3, "errors": []})
    mock_registry.get_statistics = MagicMock(return_value={"total_plugins": 3, "categories": 2})

    with patch("core.plugins.registry", mock_registry), patch("app.main_cloud.app", mock_app):
        await initialize_plugins()

        # Verify discovery was called
        mock_registry.discover_plugins.assert_called_once()

        # Verify registry stored in app state
        assert mock_app.state.plugin_registry == mock_registry


@pytest.mark.asyncio
async def test_initialize_plugins_handles_errors():
    """Test initialize_plugins handles errors gracefully"""
    from app.main_cloud import initialize_plugins

    # Mock app state
    mock_app = MagicMock()
    mock_app.state = MagicMock()

    # Mock registry that raises error
    mock_registry = MagicMock()
    mock_registry.discover_plugins = AsyncMock(side_effect=Exception("Discovery failed"))

    with patch("core.plugins.registry", mock_registry), patch("app.main_cloud.app", mock_app):
        with patch("app.main_cloud.logger") as mock_logger:
            # Should not raise
            await initialize_plugins()

            # Should log error
            mock_logger.error.assert_called()

            # Should set registry to None on error
            assert mock_app.state.plugin_registry is None


async def test_initialize_plugins_finds_plugins_directory():
    """Test initialize_plugins finds correct plugins directory"""
    from app.main_cloud import initialize_plugins

    # Mock app state
    mock_app = MagicMock()
    mock_app.state = MagicMock()

    # Mock registry
    mock_registry = MagicMock()
    mock_registry.discover_plugins = AsyncMock(return_value={"discovered": 0, "errors": []})
    mock_registry.get_statistics = MagicMock(return_value={"total_plugins": 0, "categories": 0})

    with patch("core.plugins.registry", mock_registry), patch("app.main_cloud.app", mock_app):
        with patch("pathlib.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.parent.parent = MagicMock()
            mock_path_instance.parent.parent.__truediv__ = MagicMock(
                return_value=Path("/mock/plugins")
            )
            mock_path.return_value = mock_path_instance

            await initialize_plugins()

            # Verify discover_plugins was called with correct path
            call_args = mock_registry.discover_plugins.call_args
            assert call_args is not None
            # Should be called with plugins directory and package prefix
            assert "backend.plugins" in str(call_args)










