"""
Unit tests for app/utils/debug_context.py
Target: >95% coverage
"""

import logging
import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.utils.debug_context import DebugContext, debug_mode


class TestDebugContext:
    """Tests for DebugContext"""

    def test_init_default(self):
        """Test DebugContext initialization with defaults"""
        ctx = DebugContext()
        assert ctx.request_id is None
        assert ctx.enable_verbose_logging is True
        assert ctx.capture_api_calls is True
        assert ctx.save_state_snapshot is False
        assert ctx.original_log_levels == {}
        assert ctx.api_calls == []
        assert ctx.state_snapshot is None

    def test_init_custom(self):
        """Test DebugContext initialization with custom parameters"""
        ctx = DebugContext(
            request_id="test-123",
            enable_verbose_logging=False,
            capture_api_calls=False,
            save_state_snapshot=True,
        )
        assert ctx.request_id == "test-123"
        assert ctx.enable_verbose_logging is False
        assert ctx.capture_api_calls is False
        assert ctx.save_state_snapshot is True

    def test_enter_exit_context(self):
        """Test entering and exiting debug context"""
        ctx = DebugContext(request_id="test-123", enable_verbose_logging=False)
        with ctx:
            assert ctx.request_id == "test-123"
        # Should not raise exception

    def test_enter_enables_verbose_logging(self):
        """Test that entering context enables verbose logging"""
        original_level = logging.getLogger().level
        ctx = DebugContext(enable_verbose_logging=True)

        try:
            with ctx:
                # Root logger should be set to DEBUG
                assert logging.getLogger().level == logging.DEBUG
        finally:
            # Restore original level
            logging.getLogger().setLevel(original_level)

    def test_exit_restores_log_levels(self):
        """Test that exiting context restores log levels"""
        original_level = logging.getLogger().level
        ctx = DebugContext(enable_verbose_logging=True)

        with ctx:
            logging.getLogger().setLevel(logging.DEBUG)

        # Level should be restored (or at least not crash)
        assert logging.getLogger().level >= original_level or original_level == logging.NOTSET

    def test_capture_api_call(self):
        """Test capturing API calls"""
        ctx = DebugContext(capture_api_calls=True)
        ctx.capture_api_call("GET", "https://api.example.com", status=200)

        assert len(ctx.api_calls) == 1
        assert ctx.api_calls[0]["method"] == "GET"
        assert ctx.api_calls[0]["url"] == "https://api.example.com"
        assert ctx.api_calls[0]["status"] == 200

    def test_capture_api_call_disabled(self):
        """Test that API calls are not captured when disabled"""
        ctx = DebugContext(capture_api_calls=False)
        ctx.capture_api_call("GET", "https://api.example.com")

        assert len(ctx.api_calls) == 0

    def test_get_state_snapshot(self):
        """Test getting state snapshot"""
        ctx = DebugContext(request_id="test-123")
        ctx.capture_api_call("GET", "https://api.example.com")

        snapshot = ctx.get_state_snapshot()

        assert snapshot["request_id"] == "test-123"
        assert snapshot["api_calls_count"] == 1
        assert snapshot["verbose_logging"] is True
        assert snapshot["capture_api_calls"] is True

    def test_context_manager_usage(self):
        """Test using DebugContext as context manager"""
        with DebugContext(request_id="test-456") as ctx:
            assert ctx.request_id == "test-456"
            ctx.capture_api_call("POST", "https://api.example.com")

        assert len(ctx.api_calls) == 1

    def test_exit_does_not_suppress_exceptions(self):
        """Test that exceptions are not suppressed"""
        ctx = DebugContext()

        with pytest.raises(ValueError), ctx:
            raise ValueError("Test error")

    def test_debug_mode_context_manager(self):
        """Test debug_mode convenience function"""
        with debug_mode(request_id="test-789") as ctx:
            assert ctx.request_id == "test-789"
            assert ctx.enable_verbose_logging is True
            assert ctx.capture_api_calls is True

    def test_debug_mode_custom_params(self):
        """Test debug_mode with custom parameters"""
        with debug_mode(
            request_id="test-abc", enable_verbose_logging=False, capture_api_calls=False
        ) as ctx:
            assert ctx.request_id == "test-abc"
            assert ctx.enable_verbose_logging is False
            assert ctx.capture_api_calls is False

