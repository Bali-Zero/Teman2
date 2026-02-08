"""
Pytest configuration and fixtures.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from backend.db.connection import DatabaseManager
from backend.core.cache import CacheManager


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_db():
    """Mock database connection."""
    db = MagicMock(spec=DatabaseManager)
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    db.execute = AsyncMock(return_value="INSERT 1")
    return db


@pytest_asyncio.fixture
async def mock_cache():
    """Mock cache connection."""
    cache = MagicMock(spec=CacheManager)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def sample_article_data():
    """Sample article data for tests."""
    return {
        "title": "Test Article",
        "url": "https://example.com/article",
        "content": "This is test content.",
        "author": "Test Author",
        "published_at": "2024-01-01T00:00:00",
        "category": "technology",
    }


@pytest.fixture
def sample_source_data():
    """Sample source data for tests."""
    return {
        "name": "Test Source",
        "url": "https://example.com",
        "feed_url": "https://example.com/feed",
        "is_active": True,
    }
