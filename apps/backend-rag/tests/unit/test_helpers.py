"""
Test helpers for common mock patterns
"""
from unittest.mock import AsyncMock, Mock


def create_mock_db_pool():
    """Create a properly configured mock database pool"""
    mock_pool = Mock()
    mock_conn = AsyncMock()

    # Configure async context manager for acquire()
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = Mock(return_value=mock_acquire)

    # Set default return values for common methods
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=None)

    return mock_pool, mock_conn
