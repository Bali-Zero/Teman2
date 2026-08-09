"""
Pytest conftest for backend/tests/unit/routers/ tests.

Provides common fixtures for:
- Mock authentication (get_current_user)
- Mock database pool (get_database_pool)
- FastAPI TestClient factory
- Common test data

Sets deterministic environment variables before application imports.
"""

import os
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
def mock_db_pool() -> MagicMock:
    """Mock asyncpg connection pool with async context manager support."""
    pool = MagicMock()
    conn = MagicMock()

    class _AsyncContext:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, exc_type, exc, tb):
            return False

    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=_AsyncContext())

    # Make pool.acquire() work as async context manager:
    # pool.acquire() must return an object that supports __aenter__/__aexit__
    acquire_cm = _AsyncContext()
    pool.acquire = MagicMock(return_value=acquire_cm)

    # Store conn reference for easy access in tests
    pool._mock_conn = conn
    return pool


@pytest.fixture
def mock_db_conn(mock_db_pool: AsyncMock) -> AsyncMock:
    """Direct access to the mock connection from the pool."""
    return mock_db_pool._mock_conn


@pytest.fixture
def disable_auth_middleware():
    """
    Disable HybridAuthMiddleware for tests that use main_cloud.app.

    The real settings model is used so test order cannot replace production
    config with a reduced fake module. This fixture:
    1. Sets settings.api_auth_enabled = False temporarily
    2. Resets app.middleware_stack = None so the middleware is re-instantiated
       with auth disabled on the next request

    Use this fixture in every fixture that uses `from backend.app.main_cloud import app`.
    """
    import sys

    # Get the settings object (real or mocked, whichever is active)
    config_module = sys.modules.get("backend.app.core.config")
    if config_module is not None:
        settings_obj = getattr(config_module, "settings", None)
        original_auth = getattr(settings_obj, "api_auth_enabled", None) if settings_obj else None
        if settings_obj is not None:
            try:
                settings_obj.api_auth_enabled = False
            except Exception:
                pass  # MagicMock or frozen pydantic model — skip
    else:
        settings_obj = None
        original_auth = None

    # Force middleware stack to rebuild so the new api_auth_enabled=False takes effect
    main_cloud_module = sys.modules.get("backend.app.main_cloud")
    if main_cloud_module is not None:
        app_obj = getattr(main_cloud_module, "app", None)
        if app_obj is not None:
            app_obj.middleware_stack = None

    yield

    # Restore original api_auth_enabled
    if settings_obj is not None and original_auth is not None:
        try:
            settings_obj.api_auth_enabled = original_auth
        except Exception:
            pass

    # Reset middleware stack so other tests don't inherit our disabled auth
    if main_cloud_module is not None:
        app_obj = getattr(main_cloud_module, "app", None)
        if app_obj is not None:
            app_obj.middleware_stack = None
