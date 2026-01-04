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
_mock_settings.api_keys = "test_key_1,test_key_2"
_mock_settings.api_auth_enabled = False
_mock_settings.jwt_secret_key = "test_secret_key_minimum_32_characters"
_mock_settings.jwt_algorithm = "HS256"

# Patch the config module before it's imported
# This prevents Settings() from being called during import
if "app.core.config" not in sys.modules:
    # Create a fake config module
    fake_config = type(sys)("app.core.config")
    fake_config.settings = _mock_settings

    # Create a fake Settings class that returns our mock
    class FakeSettings:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return _mock_settings

    fake_config.Settings = FakeSettings
    sys.modules["app.core.config"] = fake_config
else:
    # If already imported, patch it
    from unittest.mock import patch

    with patch("app.core.config.settings", _mock_settings):
        pass
