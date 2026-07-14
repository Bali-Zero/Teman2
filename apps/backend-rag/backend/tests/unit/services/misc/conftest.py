"""
Pytest configuration for misc services tests.
Patches settings before any imports to prevent pydantic validation errors.
Based on orchestrator conftest.py pattern.
"""

import os
from unittest.mock import MagicMock

# Set environment variables before any imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing-only")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# Create a mock settings instance that will be used
_mock_settings = MagicMock()
_mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
_mock_settings.google_api_key = "test-google-api-key"
_mock_settings.environment = "test"
_mock_settings.api_keys = "test_api_key_1,test_api_key_2"
_mock_settings.api_auth_enabled = False
_mock_settings.jwt_secret_key = "test_jwt_secret_key_for_testing_only_min_32_chars_long"
_mock_settings.jwt_algorithm = "HS256"
_mock_settings.openai_api_key = "sk-test-key-for-testing-only"
_mock_settings.qdrant_url = "http://localhost:6333"
_mock_settings.redis_url = "redis://localhost:6379/0"

# NOTE (2026-07-14, scheduler-necropsy follow-up): this conftest used to install
# a FAKE backend.app.core.config module into sys.modules at collection time,
# session-wide and without cleanup (W96 family: test state leaking beyond the
# test). Any test that later lazy-imported the real app (e.g. the unit/routers
# coverage tests importing main_cloud) got a MagicMock settings whose log_level
# exploded configure_logging with "attribute name must be string, not MagicMock".
# The env defaults above are sufficient for the real Settings() to validate,
# so the hack is gone. _mock_settings stays for fixtures that patch it locally.
