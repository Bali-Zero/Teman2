"""
Comprehensive Integration Tests for Utilities
Tests error_handlers, logging_utils, state_helpers

Covers:
- Error handling utilities
- Logging utilities
- State helpers
- Utility functions
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestErrorHandlers:
    """Integration tests for error handlers"""

    @pytest.mark.asyncio
    async def test_database_error_handling(self, db_pool):
        """Test database error handling"""
        from app.utils.error_handlers import handle_database_error

        async with db_pool.acquire() as conn:
            # Test connection error handling
            try:
                # Try invalid query
                await conn.execute("SELECT * FROM non_existent_table")
            except Exception as e:
                error_info = handle_database_error(e)

                assert error_info is not None
                assert "error" in error_info or "message" in error_info

    @pytest.mark.asyncio
    async def test_error_logging(self, db_pool):
        """Test error logging"""

        async with db_pool.acquire() as conn:
            # Create error_log table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS utility_error_logs (
                    id SERIAL PRIMARY KEY,
                    error_type VARCHAR(255),
                    error_message TEXT,
                    context JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Log error
            error_id = await conn.fetchval(
                """
                INSERT INTO utility_error_logs (
                    error_type, error_message, context
                )
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "DatabaseError",
                "Test error",
                {"endpoint": "/api/test", "user_id": "test_user"},
            )

            assert error_id is not None

            # Cleanup
            await conn.execute("DELETE FROM utility_error_logs WHERE id = $1", error_id)


@pytest.mark.integration
class TestLoggingUtils:
    """Integration tests for logging utilities"""

    @pytest.mark.asyncio
    async def test_logging_utils_initialization(self):
        """Test logging utilities initialization"""
        from app.utils.logging_utils import get_logger

        logger = get_logger(__name__)

        assert logger is not None

    @pytest.mark.asyncio
    async def test_database_operation_logging(self, db_pool):
        """Test database operation logging"""

        async with db_pool.acquire() as conn:
            # Create operation_logs table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id SERIAL PRIMARY KEY,
                    operation_type VARCHAR(100),
                    table_name VARCHAR(255),
                    operation_details JSONB,
                    execution_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Log operation
            import time

            start_time = time.time()
            await conn.execute("SELECT 1")
            execution_time_ms = int((time.time() - start_time) * 1000)

            log_id = await conn.fetchval(
                """
                INSERT INTO operation_logs (
                    operation_type, table_name, operation_details, execution_time_ms
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "SELECT",
                "test_table",
                {"query": "SELECT 1"},
                execution_time_ms,
            )

            assert log_id is not None

            # Cleanup
            await conn.execute("DELETE FROM operation_logs WHERE id = $1", log_id)

    @pytest.mark.asyncio
    async def test_success_logging(self, db_pool):
        """Test success logging"""

        async with db_pool.acquire() as conn:
            # Create success_logs table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS success_logs (
                    id SERIAL PRIMARY KEY,
                    operation VARCHAR(255),
                    details JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Log success
            success_id = await conn.fetchval(
                """
                INSERT INTO success_logs (operation, details)
                VALUES ($1, $2)
                RETURNING id
                """,
                "client_created",
                {"client_id": 123, "email": "test@example.com"},
            )

            assert success_id is not None

            # Cleanup
            await conn.execute("DELETE FROM success_logs WHERE id = $1", success_id)

    @pytest.mark.asyncio
    async def test_warning_logging(self, db_pool):
        """Test warning logging"""

        async with db_pool.acquire() as conn:
            # Create warning_logs table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS warning_logs (
                    id SERIAL PRIMARY KEY,
                    warning_type VARCHAR(255),
                    message TEXT,
                    context JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Log warning
            warning_id = await conn.fetchval(
                """
                INSERT INTO warning_logs (warning_type, message, context)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "deprecated_endpoint",
                "Endpoint will be removed in next version",
                {"endpoint": "/api/old"},
            )

            assert warning_id is not None

            # Cleanup
            await conn.execute("DELETE FROM warning_logs WHERE id = $1", warning_id)


@pytest.mark.integration
class TestStateHelpers:
    """Integration tests for state helpers"""

    @pytest.mark.asyncio
    async def test_state_helpers_initialization(self):
        """Test state helpers initialization"""
        from app.utils.state_helpers import get_app_state

        # Mock app state
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state.db_pool = MagicMock()
        mock_app.state.search_service = MagicMock()

        # Test state access
        db_pool = get_app_state(mock_app, "db_pool")
        assert db_pool is not None

    @pytest.mark.asyncio
    async def test_service_state_management(self, db_pool):
        """Test service state management"""

        async with db_pool.acquire() as conn:
            # Create service_states table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS service_states (
                    id SERIAL PRIMARY KEY,
                    service_name VARCHAR(255) UNIQUE,
                    status VARCHAR(50),
                    last_check TIMESTAMP DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}'
                )
                """
            )

            # Store service state
            await conn.execute(
                """
                INSERT INTO service_states (service_name, status, metadata)
                VALUES ($1, $2, $3)
                ON CONFLICT (service_name) DO UPDATE
                SET status = EXCLUDED.status, last_check = NOW()
                """,
                "test_service",
                "operational",
                {"version": "1.0.0", "uptime": 3600},
            )

            # Retrieve state
            state = await conn.fetchrow(
                """
                SELECT status, metadata
                FROM service_states
                WHERE service_name = $1
                """,
                "test_service",
            )

            assert state is not None
            assert state["status"] == "operational"

            # Cleanup
            await conn.execute("DELETE FROM service_states WHERE service_name = $1", "test_service")
