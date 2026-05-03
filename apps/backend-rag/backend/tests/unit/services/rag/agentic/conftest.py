"""
Pytest configuration for orchestrator tests.
Patches settings before any imports to prevent pydantic validation errors.
"""

import sys
from unittest.mock import MagicMock

# Create a mock settings instance that will be used
_mock_settings = MagicMock()
_mock_settings.database_url = "postgresql://test:5432/test"
_mock_settings.google_api_key = "test-api-key"
_mock_settings.environment = "test"
_mock_settings.log_level = "INFO"
_mock_settings.API_V1_STR = "/api/v1"
_mock_settings.PROJECT_NAME = "Nuzantara Prime"
_mock_settings.api_keys = "test_key_1,test_key_2"
_mock_settings.api_auth_enabled = False
_mock_settings.jwt_secret_key = "test_secret_key_minimum_32_characters"
_mock_settings.jwt_algorithm = "HS256"
_mock_settings.qdrant_url = "http://localhost:6333"
_mock_settings.zantara_allowed_origins = ""
_mock_settings.otel_enabled = False
_mock_settings.get_intel_pending_path = "/tmp/intel_pending"
_mock_settings.intel_pending_path = "/tmp/intel_pending"
_mock_settings.admin_api_key = None
_mock_settings.telegram_bot_token = None
_mock_settings.log_file = None
_mock_settings.embedding_model = "text-embedding-3-small"
_mock_settings.embedding_provider = "openai"
_mock_settings.enable_skill_detection = False
_mock_settings.enable_collective_memory = False
_mock_settings.enable_advanced_analytics = False
_mock_settings.enable_tool_execution = True
_mock_settings.enable_hybrid_search = (
    False  # Prevent truthy MagicMock from enabling hybrid search in tools
)

# Patch the config module before it's imported
# This prevents Settings() from being called during import
if "backend.app.core.config" not in sys.modules:
    # Create a fake config module
    fake_config = type(sys)("backend.app.core.config")
    fake_config.settings = _mock_settings

    # Create a fake Settings class that returns our mock
    class FakeSettings:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __call__(self, *args, **kwargs):
            return _mock_settings

    fake_config.Settings = FakeSettings
    sys.modules["backend.app.core.config"] = fake_config
else:
    # If already imported, patch it
    from unittest.mock import patch

    with patch("backend.app.core.config.settings", _mock_settings):
        pass
