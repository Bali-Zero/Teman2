"""
Unit tests for tracing utilities
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.utils.tracing import (
    add_span_event,
    get_tracer,
    set_span_attribute,
    set_span_status,
    trace_span,
)


class TestTracingUtilities:
    """Tests for tracing utilities"""

    def test_get_tracer_not_available(self):
        """Test getting tracer when OpenTelemetry not available"""
        with patch("app.utils.tracing.OTEL_AVAILABLE", False):
            tracer = get_tracer()
            assert tracer is None

    @patch("app.utils.tracing.OTEL_AVAILABLE", True)
    @patch("app.utils.tracing.trace")
    def test_get_tracer_available(self, mock_trace):
        """Test getting tracer when OpenTelemetry available"""
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        tracer = get_tracer("test_tracer")
        assert tracer == mock_tracer
        mock_trace.get_tracer.assert_called_once_with("test_tracer")

    @patch("app.utils.tracing.OTEL_AVAILABLE", True)
    @patch("app.utils.tracing.trace")
    def test_get_tracer_exception(self, mock_trace):
        """Test getting tracer with exception"""
        mock_trace.get_tracer.side_effect = Exception("Tracer error")

        tracer = get_tracer()
        assert tracer is None

    @patch("app.utils.tracing.OTEL_AVAILABLE", False)
    def test_trace_span_not_available(self):
        """Test trace_span when OpenTelemetry not available"""
        with trace_span("test_span") as span:
            assert span is None

    @patch("app.utils.tracing.OTEL_AVAILABLE", True)
    @patch("app.utils.tracing.get_tracer")
    def test_trace_span_available(self, mock_get_tracer):
        """Test trace_span when OpenTelemetry available"""
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_span)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_tracer.start_as_current_span.return_value = mock_context
        mock_get_tracer.return_value = mock_tracer

        with trace_span("test_span", {"key": "value"}) as span:
            assert span == mock_span
            mock_span.set_attribute.assert_called()

    @patch("app.utils.tracing.OTEL_AVAILABLE", False)
    def test_add_span_event_not_available(self):
        """Test add_span_event when OpenTelemetry not available"""
        # Should not raise exception
        add_span_event("test_event", {"key": "value"})

    @patch("app.utils.tracing.OTEL_AVAILABLE", True)
    @patch("app.utils.tracing.trace")
    def test_add_span_event_available(self, mock_trace):
        """Test add_span_event when OpenTelemetry available"""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_trace.get_current_span.return_value = mock_span

        add_span_event("test_event", {"key": "value"})
        mock_span.add_event.assert_called_once_with("test_event", attributes={"key": "value"})

    @patch("app.utils.tracing.OTEL_AVAILABLE", False)
    def test_set_span_attribute_not_available(self):
        """Test set_span_attribute when OpenTelemetry not available"""
        # Should not raise exception
        set_span_attribute("key", "value")

    @patch("app.utils.tracing.OTEL_AVAILABLE", True)
    @patch("app.utils.tracing.trace")
    def test_set_span_attribute_available(self, mock_trace):
        """Test set_span_attribute when OpenTelemetry available"""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_trace.get_current_span.return_value = mock_span

        set_span_attribute("key", "value")
        mock_span.set_attribute.assert_called_once_with("key", "value")

    @patch("app.utils.tracing.OTEL_AVAILABLE", False)
    def test_set_span_status_not_available(self):
        """Test set_span_status when OpenTelemetry not available"""
        # Should not raise exception
        set_span_status("ok")




