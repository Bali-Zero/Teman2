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


class TestDatabaseErrorLogsNoRowData:
    """A rejected row must not reach the log.

    Measured on a live Postgres 17 (2026-09-16, SAETTA R5): asyncpg puts the
    server's DETAIL into `str(e)`, and the DETAIL of a constraint violation is
    `Failing row contains (...)` — on `clients` that is the client's name,
    phone, passport number and NPWP. `handle_database_error` used to log the
    exception itself with `%s`, writing all of it into the application log.
    Builder Contract §4 makes that an output-boundary violation.

    GUILT: a sentinel value that is only present in the row data must not
    appear in what gets logged. INNOCENCE: the operator must still learn the
    error class, the SQLSTATE and the constraint name, or the cure would have
    traded a leak for a blind spot.
    """

    SENTINEL = "SENTINEL-CLIENT-NAME-9x7"

    def _violation(self):
        import asyncpg

        e = asyncpg.exceptions.CheckViolationError(
            f'new row for relation "clients" violates check constraint '
            f'"clients_tax_consultant_check"\nDETAIL:  Failing row contains '
            f"(11, {self.SENTINEL}, +62811234567, A1234567, ghost@nowhere.example)."
        )
        e.sqlstate = "23514"
        e.constraint_name = "clients_tax_consultant_check"
        e.table_name = "clients"
        return e

    def test_row_data_is_not_logged(self, caplog):
        import logging

        from backend.app.utils.error_handlers import handle_database_error

        with caplog.at_level(logging.WARNING):
            handle_database_error(self._violation())
        assert self.SENTINEL not in caplog.text
        assert "Failing row contains" not in caplog.text

    def test_the_operator_still_gets_a_usable_signature(self, caplog):
        import logging

        from backend.app.utils.error_handlers import handle_database_error

        with caplog.at_level(logging.WARNING):
            handle_database_error(self._violation())
        assert "CheckViolationError" in caplog.text
        assert "23514" in caplog.text
        assert "clients_tax_consultant_check" in caplog.text

    def test_the_client_facing_message_is_unchanged(self):
        from backend.app.utils.error_handlers import handle_database_error

        exc = handle_database_error(self._violation())
        assert exc.status_code == 400
        assert exc.detail == "Invalid data provided"
