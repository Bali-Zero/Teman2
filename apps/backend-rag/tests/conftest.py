"""
Pytest configuration and shared fixtures
Sets up Python path for imports and required environment variables
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set required environment variables BEFORE any imports that use settings
# These are required by app.core.config.Settings
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")

# Add backend directory to Python path for imports
backend_path = Path(__file__).parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# ASYNC CONTEXT MANAGER MOCK HELPERS
# ============================================================================


def create_async_cm_mock(return_value):
    """
    Create a mock that works as an async context manager.
    Use for mocking `async with pool.acquire() as conn:` patterns.

    Usage:
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value = create_async_cm_mock(mock_conn)
    """
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=return_value)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


def create_mock_db_pool(mock_conn=None):
    """
    Create a mock database pool with proper async context manager setup.

    Args:
        mock_conn: Optional AsyncMock for the connection. If None, creates one.

    Returns:
        tuple: (mock_pool, mock_conn)

    Usage:
        mock_pool, mock_conn = create_mock_db_pool()
        mock_conn.fetchrow.return_value = {"id": 1}
    """
    if mock_conn is None:
        mock_conn = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = create_async_cm_mock(mock_conn)
    return mock_pool, mock_conn


def create_mock_redis_pubsub():
    """
    Create mock Redis client and pubsub for testing redis_listener.

    Returns:
        tuple: (mock_client, mock_pubsub)

    Usage:
        mock_client, mock_pubsub = create_mock_redis_pubsub()

        async def mock_listen():
            yield {"type": "pmessage", "channel": "test", "data": "{}"}
            raise asyncio.CancelledError()

        mock_pubsub.listen.return_value = mock_listen()
    """
    mock_client = MagicMock()
    mock_pubsub = MagicMock()
    mock_pubsub.psubscribe = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_client.pubsub.return_value = mock_pubsub
    mock_client.close = AsyncMock()
    return mock_client, mock_pubsub


@pytest.fixture
def mock_db_pool():
    """Pytest fixture for mock database pool."""
    return create_mock_db_pool()


@pytest.fixture
def mock_redis():
    """Pytest fixture for mock Redis client and pubsub."""
    return create_mock_redis_pubsub()
