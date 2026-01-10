"""
Unit tests for ResponseHandler
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.routing.response_handler import ResponseHandler


@pytest.fixture
def response_handler():
    """Create response handler instance"""
    return ResponseHandler()


class TestResponseHandler:
    """Tests for ResponseHandler"""

    def test_init(self):
        """Test initialization"""
        handler = ResponseHandler()
        assert handler is not None

    def test_classify_query(self, response_handler):
        """Test query classification"""
        with patch("backend.services.routing.response_handler.classify_query_for_rag") as mock_classify:
            mock_classify.return_value = "business"

            result = response_handler.classify_query("How to open a company?")
            assert result == "business"

    def test_sanitize_response_empty(self, response_handler):
        """Test sanitizing empty response"""
        result = response_handler.sanitize_response("", "business")
        assert result == ""

    def test_sanitize_response_success(self, response_handler):
        """Test successful response sanitization"""
        with patch("backend.services.routing.response_handler.process_zantara_response") as mock_process:
            mock_process.return_value = "Sanitized response"

            result = response_handler.sanitize_response("Raw response", "business")
            assert result == "Sanitized response"

    def test_sanitize_response_error(self, response_handler):
        """Test sanitization error handling"""
        with patch("backend.services.routing.response_handler.process_zantara_response") as mock_process:
            mock_process.side_effect = Exception("Error")

            result = response_handler.sanitize_response("Raw response", "business")
            assert result == "Raw response"  # Should return original on error

    def test_sanitize_response_with_santai(self, response_handler):
        """Test sanitization with SANTAI mode"""
        with patch("backend.services.routing.response_handler.process_zantara_response") as mock_process:
            mock_process.return_value = "Sanitized"

            result = response_handler.sanitize_response("Raw response", "casual", apply_santai=True)
            assert result == "Sanitized"

    def test_sanitize_response_without_contact(self, response_handler):
        """Test sanitization without contact info"""
        with patch("backend.services.routing.response_handler.process_zantara_response") as mock_process:
            mock_process.return_value = "Sanitized"

            result = response_handler.sanitize_response(
                "Raw response", "greeting", add_contact=False
            )
            assert result == "Sanitized"
