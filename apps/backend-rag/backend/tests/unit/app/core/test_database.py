"""
Tests for database pool configuration.
Validates hardening parameters without needing a real database.
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.app.core.database import (
    _ACQUIRE_TIMEOUT,
    _COMMAND_TIMEOUT,
    _MAX_INACTIVE_CONN_LIFETIME,
    _POOL_MAX_SIZE,
    _POOL_MIN_SIZE,
    get_db_pool,
)


class TestPoolConstants:
    """Verify pool configuration constants are sensible."""

    def test_pool_min_size(self):
        assert _POOL_MIN_SIZE >= 1
        assert _POOL_MIN_SIZE <= _POOL_MAX_SIZE

    def test_pool_max_size(self):
        assert _POOL_MAX_SIZE >= 2
        assert _POOL_MAX_SIZE <= 20  # Fly.io resource constraint

    def test_command_timeout(self):
        assert _COMMAND_TIMEOUT >= 10  # At least 10s for slow queries
        assert _COMMAND_TIMEOUT <= 120  # Never wait longer than 2 min

    def test_idle_connection_lifetime(self):
        assert _MAX_INACTIVE_CONN_LIFETIME >= 60  # At least 1 min
        assert _MAX_INACTIVE_CONN_LIFETIME <= 600  # At most 10 min

    def test_acquire_timeout(self):
        assert _ACQUIRE_TIMEOUT >= 5
        assert _ACQUIRE_TIMEOUT <= 30


class TestGetDbPool:
    """Test pool creation passes correct parameters."""

    @pytest.mark.asyncio
    async def test_create_pool_params(self):
        """get_db_pool should pass hardening params to asyncpg.create_pool."""
        with (
            patch("backend.app.core.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool,
            patch("backend.app.core.database.settings") as mock_settings,
        ):
            mock_settings.database_url = "postgresql://test:test@localhost/testdb"
            mock_pool.return_value = AsyncMock()

            await get_db_pool()

            mock_pool.assert_awaited_once()
            call_kwargs = mock_pool.call_args.kwargs

            assert call_kwargs["min_size"] == _POOL_MIN_SIZE
            assert call_kwargs["max_size"] == _POOL_MAX_SIZE
            assert call_kwargs["command_timeout"] == _COMMAND_TIMEOUT
            assert call_kwargs["max_inactive_connection_lifetime"] == _MAX_INACTIVE_CONN_LIFETIME
            assert call_kwargs["statement_cache_size"] == 0

    @pytest.mark.asyncio
    async def test_create_pool_has_init_callback(self):
        """get_db_pool should set init callback for JSON codec setup."""
        with (
            patch("backend.app.core.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool,
            patch("backend.app.core.database.settings") as mock_settings,
        ):
            mock_settings.database_url = "postgresql://test:test@localhost/testdb"
            mock_pool.return_value = AsyncMock()

            await get_db_pool()

            call_kwargs = mock_pool.call_args.kwargs
            assert call_kwargs["init"] is not None
            assert callable(call_kwargs["init"])
