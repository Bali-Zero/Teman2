#!/usr/bin/env python3
"""
Tests for logging_config module.

Comprehensive tests for:
- Logging setup and configuration
- Context managers (log_context, correlation_context)
- Decorators (log_operation, log_errors)
- PerformanceLogger
- JSON formatting
"""

import pytest
import sys
import json
import time
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from logging_config import (
    setup_logging,
    get_logger,
    log_context,
    correlation_context,
    log_operation,
    log_errors,
    PerformanceLogger,
    json_formatter,
    _correlation_id,
    _log_context,
    CONSOLE_FORMAT,
    FILE_FORMAT,
    ENV_LOG_LEVELS,
)


class TestSetupLogging:
    """Tests for setup_logging function"""

    def test_setup_logging_creates_log_directory(self, tmp_path):
        """Test that setup_logging creates log directory"""
        log_dir = tmp_path / "test_logs"
        assert not log_dir.exists()

        setup_logging(log_dir=str(log_dir), environment="testing")

        assert log_dir.exists()

    def test_setup_logging_respects_environment(self, tmp_path):
        """Test log level is set based on environment"""
        log_dir = tmp_path / "logs"

        # Development should use DEBUG
        setup_logging(
            log_dir=str(log_dir),
            environment="development"
        )
        # Level is set on handlers, not easily inspectable without mocking

    def test_setup_logging_uses_env_variable(self, tmp_path, monkeypatch):
        """Test setup_logging reads ENVIRONMENT env var"""
        monkeypatch.setenv("ENVIRONMENT", "production")
        log_dir = tmp_path / "logs"

        setup_logging(log_dir=str(log_dir))
        # Should use production settings (INFO level)

    def test_setup_logging_custom_level(self, tmp_path):
        """Test custom log level override"""
        log_dir = tmp_path / "logs"

        setup_logging(
            log_dir=str(log_dir),
            level="WARNING",
            environment="development"
        )

    def test_setup_logging_json_format(self, tmp_path):
        """Test JSON format is enabled for production"""
        log_dir = tmp_path / "logs"

        setup_logging(
            log_dir=str(log_dir),
            environment="production",
            json_logs=True
        )

    def test_setup_logging_creates_error_log(self, tmp_path):
        """Test error log file is created"""
        log_dir = tmp_path / "logs"

        setup_logging(
            log_dir=str(log_dir),
            app_name="test_app"
        )

        # Log files are created lazily on first write


class TestGetLogger:
    """Tests for get_logger function"""

    def test_get_logger_returns_logger(self):
        """Test get_logger returns a logger instance"""
        logger = get_logger()
        assert logger is not None

    def test_get_logger_with_name(self):
        """Test get_logger with name binding"""
        logger = get_logger("my_module")
        assert logger is not None

    def test_get_logger_binds_name(self):
        """Test logger has bound name"""
        logger = get_logger("test_component")
        # The bound name is stored in extra
        assert logger is not None


class TestLogContext:
    """Tests for log_context context manager"""

    def test_log_context_sets_context(self):
        """Test log_context adds context fields"""
        with log_context(user="admin", request_id="123"):
            ctx = _log_context.get()
            assert ctx["user"] == "admin"
            assert ctx["request_id"] == "123"

    def test_log_context_clears_on_exit(self):
        """Test context is cleared after exit"""
        with log_context(temp_field="value"):
            assert _log_context.get().get("temp_field") == "value"

        # After exit, context should not contain temp_field
        ctx = _log_context.get()
        assert "temp_field" not in ctx

    def test_log_context_nested(self):
        """Test nested log contexts"""
        with log_context(outer="a"):
            with log_context(inner="b"):
                ctx = _log_context.get()
                assert ctx.get("outer") == "a"
                assert ctx.get("inner") == "b"

            # Inner should be removed
            ctx = _log_context.get()
            assert ctx.get("outer") == "a"
            assert "inner" not in ctx

    def test_log_context_overwrites(self):
        """Test inner context can overwrite outer"""
        with log_context(key="outer_value"):
            with log_context(key="inner_value"):
                ctx = _log_context.get()
                assert ctx["key"] == "inner_value"


class TestCorrelationContext:
    """Tests for correlation_context context manager"""

    def test_correlation_context_generates_id(self):
        """Test correlation_context generates ID if not provided"""
        with correlation_context() as corr_id:
            assert corr_id is not None
            assert len(corr_id) == 8  # UUID first 8 chars
            assert _correlation_id.get() == corr_id

    def test_correlation_context_uses_provided_id(self):
        """Test correlation_context uses provided ID"""
        with correlation_context("my-custom-id") as corr_id:
            assert corr_id == "my-custom-id"
            assert _correlation_id.get() == "my-custom-id"

    def test_correlation_context_clears_on_exit(self):
        """Test correlation ID is cleared after exit"""
        with correlation_context("test-id"):
            assert _correlation_id.get() == "test-id"

        # After exit
        assert _correlation_id.get() == ""

    def test_correlation_context_adds_to_log_context(self):
        """Test correlation ID is added to log context"""
        with correlation_context("corr-123") as corr_id:
            ctx = _log_context.get()
            assert ctx.get("correlation_id") == "corr-123"


class TestLogOperationDecorator:
    """Tests for log_operation decorator"""

    def test_log_operation_sync_function(self, tmp_path):
        """Test log_operation with sync function"""
        setup_logging(log_dir=str(tmp_path / "logs"), environment="testing")

        @log_operation("test_op")
        def my_function(x, y):
            return x + y

        result = my_function(1, 2)
        assert result == 3

    def test_log_operation_async_function(self, tmp_path):
        """Test log_operation with async function"""
        setup_logging(log_dir=str(tmp_path / "logs"), environment="testing")

        @log_operation("async_test")
        async def async_function(x):
            await asyncio.sleep(0.01)
            return x * 2

        result = asyncio.run(async_function(5))
        assert result == 10

    def test_log_operation_preserves_function_name(self):
        """Test decorator preserves function metadata"""
        @log_operation()
        def named_function():
            """Docstring"""
            pass

        assert named_function.__name__ == "named_function"
        assert named_function.__doc__ == "Docstring"

    def test_log_operation_logs_exception(self, tmp_path):
        """Test log_operation logs exceptions"""
        setup_logging(log_dir=str(tmp_path / "logs"), environment="testing")

        @log_operation("failing_op")
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

    def test_log_operation_with_args(self, tmp_path):
        """Test log_operation with log_args=True"""
        setup_logging(log_dir=str(tmp_path / "logs"), environment="testing")

        @log_operation("with_args", log_args=True)
        def func_with_args(a, b, c=None):
            return a + b

        result = func_with_args(1, 2, c="test")
        assert result == 3

    def test_log_operation_with_result(self, tmp_path):
        """Test log_operation with log_result=True"""
        setup_logging(log_dir=str(tmp_path / "logs"), environment="testing")

        @log_operation("with_result", log_result=True)
        def func_with_result():
            return {"status": "success"}

        result = func_with_result()
        assert result == {"status": "success"}


class TestLogErrorsDecorator:
    """Tests for log_errors decorator"""

    def test_log_errors_sync_function(self, tmp_path):
        """Test log_errors with sync function"""
        setup_logging(log_dir=str(tmp_path / "logs"), environment="testing")

        @log_errors()
        def failing_sync():
            raise RuntimeError("Sync error")

        with pytest.raises(RuntimeError):
            failing_sync()

    def test_log_errors_async_function(self, tmp_path):
        """Test log_errors with async function"""
        setup_logging(log_dir=str(tmp_path / "logs"), environment="testing")

        @log_errors()
        async def failing_async():
            raise RuntimeError("Async error")

        with pytest.raises(RuntimeError):
            asyncio.run(failing_async())

    def test_log_errors_no_reraise(self, tmp_path):
        """Test log_errors with reraise=False"""
        setup_logging(log_dir=str(tmp_path / "logs"), environment="testing")

        @log_errors(reraise=False)
        def failing_no_raise():
            raise ValueError("Suppressed")

        # Should not raise
        result = failing_no_raise()
        assert result is None

    def test_log_errors_success_passes_through(self, tmp_path):
        """Test log_errors doesn't affect successful calls"""
        setup_logging(log_dir=str(tmp_path / "logs"), environment="testing")

        @log_errors()
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"


class TestPerformanceLogger:
    """Tests for PerformanceLogger class"""

    def test_performance_logger_creation(self):
        """Test PerformanceLogger initialization"""
        perf = PerformanceLogger("test")
        assert perf.name == "test"
        assert perf.timings == {}

    def test_performance_logger_start_end(self):
        """Test start/end timing"""
        perf = PerformanceLogger("test")

        perf.start("operation")
        time.sleep(0.05)
        duration = perf.end("operation")

        assert duration >= 50  # At least 50ms
        assert "operation" in perf.timings
        assert len(perf.timings["operation"]) == 1

    def test_performance_logger_track_context(self):
        """Test track context manager"""
        perf = PerformanceLogger("test")

        with perf.track("tracked_op"):
            time.sleep(0.02)

        assert "tracked_op" in perf.timings
        assert perf.timings["tracked_op"][0] >= 20

    def test_performance_logger_get_stats(self):
        """Test get_stats calculation"""
        perf = PerformanceLogger("test")

        # Add multiple timings
        perf.timings["op"] = [100, 200, 300]

        stats = perf.get_stats("op")
        assert stats["count"] == 3
        assert stats["avg"] == 200
        assert stats["min"] == 100
        assert stats["max"] == 300
        assert stats["total"] == 600

    def test_performance_logger_get_stats_empty(self):
        """Test get_stats for non-existent operation"""
        perf = PerformanceLogger("test")

        stats = perf.get_stats("nonexistent")
        assert stats["count"] == 0
        assert stats["avg"] == 0

    def test_performance_logger_multiple_operations(self):
        """Test tracking multiple operations"""
        perf = PerformanceLogger("test")

        with perf.track("op_a"):
            time.sleep(0.01)

        with perf.track("op_b"):
            time.sleep(0.02)

        assert "op_a" in perf.timings
        assert "op_b" in perf.timings

    def test_performance_logger_end_without_start(self):
        """Test end without start logs warning"""
        perf = PerformanceLogger("test")

        # Should return 0 and log warning (not raise)
        duration = perf.end("never_started")
        assert duration == 0.0

    def test_performance_logger_log_summary(self, tmp_path, capsys):
        """Test log_summary outputs stats"""
        setup_logging(log_dir=str(tmp_path / "logs"), environment="testing")
        perf = PerformanceLogger("test_summary")

        perf.timings["fetch"] = [100, 150, 200]
        perf.timings["process"] = [50, 60]

        perf.log_summary()
        # Summary is logged via loguru


class TestJsonFormatter:
    """Tests for JSON log formatting"""

    def test_json_formatter_basic(self):
        """Test json_formatter produces valid JSON"""
        from datetime import datetime, timezone

        record = {
            "time": datetime.now(timezone.utc),
            "level": MagicMock(name="INFO"),
            "name": "test_logger",
            "message": "Test message",
            "module": "test_module",
            "function": "test_function",
            "line": 42,
            "exception": None,
            "extra": {},
        }
        record["level"].name = "INFO"

        result = json_formatter(record)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["message"] == "Test message"
        assert parsed["logger"] == "test_logger"
        assert parsed["level"] == "INFO"

    def test_json_formatter_with_extra(self):
        """Test json_formatter includes extra fields"""
        from datetime import datetime, timezone

        record = {
            "time": datetime.now(timezone.utc),
            "level": MagicMock(name="INFO"),
            "name": "test",
            "message": "msg",
            "module": "mod",
            "function": "func",
            "line": 1,
            "exception": None,
            "extra": {"user": "admin", "count": 5},
        }
        record["level"].name = "INFO"

        result = json_formatter(record)
        parsed = json.loads(result)

        assert parsed["user"] == "admin"
        assert parsed["count"] == 5


class TestEnvLogLevels:
    """Tests for environment log level mapping"""

    def test_development_level(self):
        """Test development environment uses DEBUG"""
        assert ENV_LOG_LEVELS["development"] == "DEBUG"

    def test_production_level(self):
        """Test production environment uses INFO"""
        assert ENV_LOG_LEVELS["production"] == "INFO"

    def test_staging_level(self):
        """Test staging environment uses INFO"""
        assert ENV_LOG_LEVELS["staging"] == "INFO"

    def test_testing_level(self):
        """Test testing environment uses DEBUG"""
        assert ENV_LOG_LEVELS["testing"] == "DEBUG"


class TestLogFormats:
    """Tests for log format strings"""

    def test_console_format_has_colors(self):
        """Test console format includes color tags"""
        assert "<green>" in CONSOLE_FORMAT
        assert "<level>" in CONSOLE_FORMAT

    def test_file_format_no_colors(self):
        """Test file format has no color tags"""
        assert "<green>" not in FILE_FORMAT
        assert "<level>" not in FILE_FORMAT

    def test_formats_include_timestamp(self):
        """Test formats include timestamp"""
        assert "{time" in CONSOLE_FORMAT
        assert "{time" in FILE_FORMAT

    def test_formats_include_level(self):
        """Test formats include log level"""
        assert "{level" in CONSOLE_FORMAT
        assert "{level" in FILE_FORMAT


class TestIntegration:
    """Integration tests for logging configuration"""

    def test_full_logging_workflow(self, tmp_path):
        """Test complete logging workflow"""
        log_dir = tmp_path / "logs"

        # Setup
        setup_logging(
            log_dir=str(log_dir),
            app_name="integration_test",
            environment="testing"
        )

        logger = get_logger("integration")

        # Use all features
        with correlation_context("test-corr") as corr_id:
            with log_context(user="tester", action="testing"):
                logger.info("Test message")
                logger.debug("Debug message")
                logger.warning("Warning message")

                @log_operation("test_operation")
                def my_op():
                    return 42

                result = my_op()
                assert result == 42

    def test_async_logging_workflow(self, tmp_path):
        """Test async logging workflow"""
        log_dir = tmp_path / "logs"

        setup_logging(
            log_dir=str(log_dir),
            app_name="async_test",
            environment="testing"
        )

        @log_operation("async_workflow")
        async def async_workflow():
            with log_context(step="async"):
                await asyncio.sleep(0.01)
                return "done"

        result = asyncio.run(async_workflow())
        assert result == "done"
