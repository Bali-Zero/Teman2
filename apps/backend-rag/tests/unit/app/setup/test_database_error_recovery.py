"""
Tests for database error recovery.

Tests the new error handling features:
- Retry logic with exponential backoff
- Transient vs permanent error classification
- Health check loop
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from backend.app.setup.service_initializer import initialize_database_services, _is_transient_error


@pytest.fixture
def mock_app():
    """Create mock FastAPI app."""
    app = MagicMock()
    app.state = MagicMock()
    return app


@pytest.mark.asyncio
async def test_is_transient_error_connection():
    """Test that connection errors are transient."""
    error = ConnectionError("Connection timeout")
    assert _is_transient_error(error) == True


@pytest.mark.asyncio
async def test_is_transient_error_timeout():
    """Test that timeout errors are transient."""
    error = Exception("timeout occurred")
    assert _is_transient_error(error) == True


@pytest.mark.asyncio
async def test_is_transient_error_too_many_connections():
    """Test that 'too many connections' errors are transient."""
    error = Exception("too many connections")
    assert _is_transient_error(error) == True


@pytest.mark.asyncio
async def test_is_transient_error_permanent():
    """Test that permanent errors are not transient."""
    error = ValueError("Invalid configuration")
    assert _is_transient_error(error) == False


@pytest.mark.asyncio
async def test_database_init_retries_on_transient_error(mock_app):
    """Test that database init retries on transient errors."""
    with patch("backend.app.setup.service_initializer.settings") as mock_settings:
        mock_settings.database_url = "postgresql://test"

        call_count = 0

        def mock_create_pool(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection timeout")

            # Return mock pool on success - properly set up async context manager
            mock_pool = MagicMock(spec=asyncpg.Pool)
            mock_conn = MagicMock()
            mock_conn.fetchval = AsyncMock(return_value=1)

            # Create proper async context manager for acquire()
            async_cm = MagicMock()
            async_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            async_cm.__aexit__ = AsyncMock(return_value=None)
            mock_pool.acquire.return_value = async_cm

            return mock_pool

        with patch("asyncpg.create_pool", side_effect=mock_create_pool):
            with patch(
                "backend.app.setup.service_initializer.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep:
                with patch(
                    "backend.app.setup.service_initializer.init_timesheet_service", create=True
                ) as mock_init:
                    mock_service = MagicMock()
                    mock_service.start_auto_logout_monitor = AsyncMock()
                    mock_init.return_value = mock_service

                    with patch(
                        "backend.app.setup.service_initializer._database_health_check_loop",
                        new_callable=AsyncMock,
                    ):
                        pool = await initialize_database_services(mock_app)

                    # Should have retried (with sleep being called for backoff)
                    assert call_count == 3
                    assert mock_sleep.call_count == 2  # Sleep called between retries


@pytest.mark.asyncio
async def test_database_init_fails_on_permanent_error(mock_app):
    """Test that database init fails immediately on permanent errors."""
    with patch("backend.app.setup.service_initializer.settings") as mock_settings:
        mock_settings.database_url = "postgresql://test"

        with patch("asyncpg.create_pool", side_effect=ValueError("Invalid configuration")):
            pool = await initialize_database_services(mock_app)

            # Should not retry permanent errors
            assert pool is None


@pytest.mark.asyncio
async def test_database_health_check_loop():
    """Test database health check loop."""
    pool = MagicMock(spec=asyncpg.Pool)
    conn = MagicMock()
    conn.execute = AsyncMock()

    # Setup async context manager properly
    async_cm = MagicMock()
    async_cm.__aenter__ = AsyncMock(return_value=conn)
    async_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = async_cm

    from backend.app.setup.service_initializer import _database_health_check_loop

    # Track sleep calls to control loop iterations
    # Health check loop: sleep -> acquire -> check -> loop
    # We need at least 1 sleep to pass, then acquire happens, then cancel on 2nd sleep
    sleep_count = 0

    async def mock_sleep(seconds):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            raise asyncio.CancelledError()  # Stop after first full iteration
        # First sleep passes through to allow acquire to be called

    with patch("backend.app.setup.service_initializer.asyncio.sleep", side_effect=mock_sleep):
        with patch("backend.app.setup.service_initializer.service_registry"):
            task = asyncio.create_task(_database_health_check_loop(pool))

            try:
                await task
            except asyncio.CancelledError:
                pass

    # Verify pool was checked at least once (after first sleep)
    assert pool.acquire.called
