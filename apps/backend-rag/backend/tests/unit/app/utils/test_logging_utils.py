"""
Unit tests for logging_utils
Target: >95% coverage
"""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.utils.logging_utils import (
    LOG_LEVELS,
    get_logger,
    log_database_operation,
    log_endpoint_call,
    log_error,
    log_success,
    log_warning,
)


class TestLogLevels:
    """Tests for LOG_LEVELS constant"""

    def test_log_levels_values(self):
        """Test that LOG_LEVELS contains correct values"""
        assert LOG_LEVELS["DEBUG"] == logging.DEBUG
        assert LOG_LEVELS["INFO"] == logging.INFO
        assert LOG_LEVELS["WARNING"] == logging.WARNING
        assert LOG_LEVELS["ERROR"] == logging.ERROR
        assert LOG_LEVELS["CRITICAL"] == logging.CRITICAL


class TestGetLogger:
    """Tests for get_logger function"""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a Logger instance"""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_different_modules(self):
        """Test that different module names return different loggers"""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name == "module1"
        assert logger2.name == "module2"
        assert logger1 is not logger2

    def test_get_logger_same_module(self):
        """Test that same module name returns same logger"""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")

        assert logger1 is logger2  # Should be same instance


class TestLogEndpointCall:
    """Tests for log_endpoint_call function"""

    def test_log_endpoint_call_basic(self):
        """Test basic endpoint call logging"""
        logger = MagicMock()

        log_endpoint_call(logger, "/api/test", "GET")

        logger.info.assert_called_once()
        call_args = logger.info.call_args[0][0]
        assert "/api/test" in call_args
        assert "GET" in call_args

    def test_log_endpoint_call_with_user(self):
        """Test endpoint call logging with user email"""
        logger = MagicMock()

        log_endpoint_call(logger, "/api/test", "POST", user_email="user@example.com")

        logger.info.assert_called_once()
        # Check that extra context contains user
        call_kwargs = logger.info.call_args[1]
        assert "extra" in call_kwargs
        assert call_kwargs["extra"]["context"]["user"] == "user@example.com"

    def test_log_endpoint_call_with_kwargs(self):
        """Test endpoint call logging with additional kwargs"""
        logger = MagicMock()

        log_endpoint_call(
            logger,
            "/api/test",
            "GET",
            user_email="user@example.com",
            session_id="session123",
            duration_ms=150,
        )

        logger.info.assert_called_once()
        # Check that extra context contains kwargs
        call_kwargs = logger.info.call_args[1]
        assert "extra" in call_kwargs
        context = call_kwargs["extra"]["context"]
        assert context["session_id"] == "session123"
        assert context["duration_ms"] == 150

    def test_log_endpoint_call_no_user(self):
        """Test endpoint call logging without user"""
        logger = MagicMock()

        log_endpoint_call(logger, "/api/test", "GET")

        logger.info.assert_called_once()
        # Should not contain user-related info
        call_args = logger.info.call_args[0][0]
        assert isinstance(call_args, str)

    def test_log_endpoint_call_different_methods(self):
        """Test endpoint call logging with different HTTP methods"""
        logger = MagicMock()

        for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            log_endpoint_call(logger, "/api/test", method)
            call_args = logger.info.call_args[0][0]
            assert method in call_args
            logger.reset_mock()

    def test_log_endpoint_call_with_none_user(self):
        """Test endpoint call logging with None user"""
        logger = MagicMock()

        log_endpoint_call(logger, "/api/test", "GET", user_email=None)

        logger.info.assert_called_once()
        # Should handle None gracefully
        call_args = logger.info.call_args[0][0]
        assert isinstance(call_args, str)


class TestLogSuccess:
    """Tests for log_success function"""

    def test_log_success_basic(self):
        """Test basic success logging"""
        logger = MagicMock()

        log_success(logger, "Operation completed")

        logger.info.assert_called_once()
        call_args = logger.info.call_args[0][0]
        assert "Operation completed" in call_args
        assert "✅" in call_args

    def test_log_success_with_kwargs(self):
        """Test success logging with kwargs"""
        logger = MagicMock()

        log_success(logger, "Operation completed", user_id="user123", duration_ms=100)

        logger.info.assert_called_once()
        call_kwargs = logger.info.call_args[1]
        assert "extra" in call_kwargs
        assert call_kwargs["extra"]["context"]["user_id"] == "user123"
        assert call_kwargs["extra"]["context"]["duration_ms"] == 100

    def test_log_success_no_kwargs(self):
        """Test success logging without kwargs"""
        logger = MagicMock()

        log_success(logger, "Operation completed")

        logger.info.assert_called_once()
        call_kwargs = logger.info.call_args[1]
        assert call_kwargs["extra"] is None


class TestLogError:
    """Tests for log_error function"""

    def test_log_error_basic(self):
        """Test basic error logging"""
        logger = MagicMock()

        log_error(logger, "Operation failed")

        logger.error.assert_called_once()
        call_args = logger.error.call_args[0][0]
        assert "Operation failed" in call_args
        assert "❌" in call_args

    def test_log_error_with_exception(self):
        """Test error logging with exception"""
        logger = MagicMock()
        error = ValueError("Test error")

        log_error(logger, "Operation failed", error=error)

        logger.error.assert_called_once()
        call_kwargs = logger.error.call_args[1]
        assert call_kwargs["exc_info"] is True
        assert "extra" in call_kwargs
        assert call_kwargs["extra"]["context"]["error"] == "Test error"

    def test_log_error_without_exception(self):
        """Test error logging without exception"""
        logger = MagicMock()

        log_error(logger, "Operation failed", exc_info=False)

        logger.error.assert_called_once()
        call_kwargs = logger.error.call_args[1]
        assert call_kwargs["exc_info"] is False

    def test_log_error_with_kwargs(self):
        """Test error logging with kwargs"""
        logger = MagicMock()

        log_error(logger, "Operation failed", user_id="user123", endpoint="/api/test")

        logger.error.assert_called_once()
        call_kwargs = logger.error.call_args[1]
        assert "extra" in call_kwargs
        assert call_kwargs["extra"]["context"]["user_id"] == "user123"
        assert call_kwargs["extra"]["context"]["endpoint"] == "/api/test"


class TestLogWarning:
    """Tests for log_warning function"""

    def test_log_warning_basic(self):
        """Test basic warning logging"""
        logger = MagicMock()

        log_warning(logger, "This is a warning")

        logger.warning.assert_called_once()
        call_args = logger.warning.call_args[0][0]
        assert "This is a warning" in call_args
        assert "⚠️" in call_args

    def test_log_warning_with_kwargs(self):
        """Test warning logging with kwargs"""
        logger = MagicMock()

        log_warning(logger, "This is a warning", reason="rate_limit", retry_after=60)

        logger.warning.assert_called_once()
        call_kwargs = logger.warning.call_args[1]
        assert "extra" in call_kwargs
        assert call_kwargs["extra"]["context"]["reason"] == "rate_limit"
        assert call_kwargs["extra"]["context"]["retry_after"] == 60


class TestLogDatabaseOperation:
    """Tests for log_database_operation function"""

    def test_log_database_operation_basic(self):
        """Test basic database operation logging"""
        logger = MagicMock()

        log_database_operation(logger, "SELECT", "users")

        logger.debug.assert_called_once()
        call_args = logger.debug.call_args[0][0]
        assert "SELECT" in call_args
        assert "users" in call_args
        assert "🗄️" in call_args

    def test_log_database_operation_with_record_id(self):
        """Test database operation logging with record ID"""
        logger = MagicMock()

        log_database_operation(logger, "UPDATE", "users", record_id=123)

        logger.debug.assert_called_once()
        call_kwargs = logger.debug.call_args[1]
        assert "extra" in call_kwargs
        assert call_kwargs["extra"]["context"]["record_id"] == 123

    def test_log_database_operation_with_kwargs(self):
        """Test database operation logging with kwargs"""
        logger = MagicMock()

        log_database_operation(
            logger, "INSERT", "users", record_id=456, user_email="test@example.com"
        )

        logger.debug.assert_called_once()
        call_kwargs = logger.debug.call_args[1]
        assert "extra" in call_kwargs
        context = call_kwargs["extra"]["context"]
        assert context["operation"] == "INSERT"
        assert context["table"] == "users"
        assert context["record_id"] == 456
        assert context["user_email"] == "test@example.com"

    def test_log_database_operation_different_operations(self):
        """Test database operation logging with different operations"""
        logger = MagicMock()

        for operation in ["CREATE", "UPDATE", "DELETE", "SELECT"]:
            log_database_operation(logger, operation, "test_table")
            call_args = logger.debug.call_args[0][0]
            assert operation in call_args
            logger.reset_mock()
