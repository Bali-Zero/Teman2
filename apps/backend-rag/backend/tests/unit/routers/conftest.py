"""
Pytest conftest for backend/tests/unit/routers/ tests.

Provides common fixtures for:
- Mock authentication (get_current_user)
- Mock database pool (get_database_pool)
- FastAPI TestClient factory
- Common test data

Patches settings and env vars before any imports to prevent
pydantic validation errors.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set environment variables before any imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing-only")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")

# Create a mock settings instance
_mock_settings = MagicMock()
_mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
_mock_settings.google_api_key = "test-google-api-key"
_mock_settings.environment = "test"
_mock_settings.log_level = "INFO"
_mock_settings.API_V1_STR = "/api/v1"
_mock_settings.PROJECT_NAME = "Nuzantara Prime"
_mock_settings.api_keys = "test_api_key_1,test_api_key_2"
_mock_settings.api_auth_enabled = False
_mock_settings.jwt_secret_key = "test_jwt_secret_key_for_testing_only_min_32_chars_long"
_mock_settings.jwt_algorithm = "HS256"
_mock_settings.openai_api_key = "sk-test-key-for-testing-only"
_mock_settings.qdrant_url = "http://localhost:6333"
_mock_settings.redis_url = "redis://localhost:6379/0"
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
_mock_settings.COMPANY_NAME = "Bali Zero"
_mock_settings.ollama_url = "http://localhost:11434"
_mock_settings.intel_scraper_api_key = "test-intel-api-key"

# Patch config module before any imports
if "backend.app.core.config" not in sys.modules:
    fake_config = type(sys)("backend.app.core.config")
    fake_config.settings = _mock_settings

    class FakeSettings:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __call__(self, *args, **kwargs):
            return _mock_settings

    fake_config.Settings = FakeSettings
    sys.modules["backend.app.core.config"] = fake_config


# ============================================
# COMMON FIXTURES
# ============================================


@pytest.fixture
def mock_current_user() -> dict:
    """Standard authenticated user for testing."""
    return {
        "id": "user-uuid-123",
        "email": "test@balizero.com",
        "role": "admin",
        "full_name": "Test User",
    }


@pytest.fixture
def mock_client_user() -> dict:
    """Client-role user for portal testing."""
    return {
        "id": "client-uuid-456",
        "email": "client@example.com",
        "role": "client",
        "full_name": "Test Client",
    }


@pytest.fixture
def mock_db_pool() -> AsyncMock:
    """Mock asyncpg connection pool with context manager support."""
    pool = AsyncMock()
    conn = AsyncMock()

    # Make pool.acquire() work as async context manager
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    # Store conn reference for easy access in tests
    pool._mock_conn = conn
    return pool


@pytest.fixture
def mock_db_conn(mock_db_pool: AsyncMock) -> AsyncMock:
    """Direct access to the mock connection from the pool."""
    return mock_db_pool._mock_conn
