"""
Unit tests for error_handlers
Target: >95% coverage
"""

import sys
from pathlib import Path

import asyncpg
from fastapi import HTTPException

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.utils.error_handlers import handle_database_error


class TestHandleDatabaseError:
    """Tests for handle_database_error function"""

    def test_handle_unique_violation_error(self):
        """Test handling UniqueViolationError"""
        error = asyncpg.UniqueViolationError("duplicate key value")
        result = handle_database_error(error)

        assert isinstance(result, HTTPException)
        assert result.status_code == 400
        assert "already exists" in result.detail.lower()

    def test_handle_foreign_key_violation_error(self):
        """Test handling ForeignKeyViolationError"""
        error = asyncpg.ForeignKeyViolationError("foreign key violation")
        result = handle_database_error(error)

        assert isinstance(result, HTTPException)
        assert result.status_code == 400
        assert "does not exist" in result.detail.lower()

    def test_handle_check_violation_error(self):
        """Test handling CheckViolationError"""
        error = asyncpg.CheckViolationError("check constraint violation")
        result = handle_database_error(error)

        assert isinstance(result, HTTPException)
        assert result.status_code == 400
        assert "invalid data" in result.detail.lower()

    def test_handle_generic_postgres_error(self):
        """Test handling generic PostgresError"""
        error = asyncpg.PostgresError("generic database error")
        result = handle_database_error(error)

        assert isinstance(result, HTTPException)
        assert result.status_code == 503
        assert "temporarily unavailable" in result.detail.lower()

    def test_handle_other_postgres_error_types(self):
        """Test handling other PostgresError types"""

        # Test with a different PostgresError subclass
        class CustomPostgresError(asyncpg.PostgresError):
            pass

        error = CustomPostgresError("custom error")
        result = handle_database_error(error)

        assert isinstance(result, HTTPException)
        assert result.status_code == 503

    def test_handle_generic_exception(self):
        """Test handling generic Exception"""
        error = ValueError("generic error")
        result = handle_database_error(error)

        assert isinstance(result, HTTPException)
        assert result.status_code == 500
        assert "internal server error" in result.detail.lower()

    def test_handle_none_error(self):
        """Test handling None (edge case)"""
        result = handle_database_error(None)

        assert isinstance(result, HTTPException)
        assert result.status_code == 500

    def test_handle_keyboard_interrupt(self):
        """Test handling KeyboardInterrupt"""
        error = KeyboardInterrupt()
        result = handle_database_error(error)

        assert isinstance(result, HTTPException)
        assert result.status_code == 500

    def test_handle_connection_error(self):
        """Test handling connection-related PostgresError"""
        error = asyncpg.PostgresError("connection failed")
        result = handle_database_error(error)

        assert isinstance(result, HTTPException)
        assert result.status_code == 503
