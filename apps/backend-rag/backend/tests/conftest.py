"""
Root conftest for all backend tests.

Sets up environment variables and shared fixtures BEFORE any module is imported.
This prevents pydantic validation errors and real API key requirements.

Shared fixtures: mock_db_pool, mock_qdrant_client, mock_redis
"""

import os
from unittest.mock import AsyncMock, MagicMock

# ============================================================================
# Environment Variables — must be set FIRST, before any import
# Covers: EmbeddingsGenerator, Settings validation, JWT, WhatsApp, Instagram
# ============================================================================

os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing-only-nuzantara")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test_token")
os.environ.setdefault("EMBEDDING_PROVIDER", "openai")
os.environ.setdefault("EMBEDDING_MODEL", "text-embedding-3-small")

# Some SDK import chains load `mcp.types`, which asks pydantic to create
# RootModel generics before `pydantic.root_model` has been registered in
# sys.modules on the local dev venv. Import it here before test modules pull
# portal/multimodal services through router imports.
import pydantic.root_model  # noqa: E402,F401


# ============================================================================
# Shared fixtures
# ============================================================================

import pytest  # noqa: E402 — must come after env setup


@pytest.fixture
def mock_db_pool():
    """Standard mock asyncpg connection pool.

    Supports: async with pool.acquire() as conn
              async with conn.transaction()  (no-op async context manager)
    Usage: pool, conn = mock_db_pool
    """
    pool = MagicMock()
    conn = AsyncMock()

    class _AsyncCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    class _TransactionCtx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=_AsyncCtx())
    # conn.transaction() must return an async context manager, not a coroutine.
    # AsyncMock would make it a coroutine; use MagicMock returning _TransactionCtx.
    conn.transaction = MagicMock(return_value=_TransactionCtx())
    return pool, conn


@pytest.fixture
def mock_qdrant_client():
    """Standard mock Qdrant client."""
    client = AsyncMock()
    client.search = AsyncMock(return_value=[])
    client.upsert = AsyncMock(return_value=None)
    client.delete = AsyncMock(return_value=None)
    client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
    return client


@pytest.fixture
def mock_redis():
    """Standard mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.keys = AsyncMock(return_value=[])
    return redis
