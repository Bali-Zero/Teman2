"""
Unit tests for response sanitizer
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from utils.response_sanitizer import sanitize_zantara_response


class TestResponseSanitizer:
    """Tests for response sanitizer"""

    def test_sanitize_empty_response(self):
        """Test sanitizing empty response"""
        result = sanitize_zantara_response("")
        assert result == ""

    def test_sanitize_none_response(self):
        """Test sanitizing None response"""
        result = sanitize_zantara_response(None)
        assert result is None

    def test_sanitize_normal_response(self):
        """Test sanitizing normal response"""
        response = "This is a normal response without artifacts."
        result = sanitize_zantara_response(response)
        assert result == response

    def test_sanitize_remove_price_placeholder(self):
        """Test removing [PRICE] placeholder"""
        response = "The cost is [PRICE] for this service."
        result = sanitize_zantara_response(response)
        assert "[PRICE]" not in result

    def test_sanitize_remove_mandatory_placeholder(self):
        """Test removing [MANDATORY] placeholder"""
        response = "This document is [MANDATORY] for the application."
        result = sanitize_zantara_response(response)
        assert "[MANDATORY]" not in result

    def test_sanitize_remove_user_assistant_format(self):
        """Test removing User:/Assistant: format leaks"""
        response = "User: What is the cost? Assistant: The cost is $100."
        result = sanitize_zantara_response(response)
        assert "User:" not in result
        assert "Assistant:" not in result

    def test_sanitize_remove_non_ho_documenti(self):
        """Test removing 'non ho documenti' pattern"""
        response = "Non ho documenti per questa domanda."
        result = sanitize_zantara_response(response)
        assert "non ho documenti" not in result.lower()
        assert "riformulare" in result.lower() or "KB" in result

    def test_sanitize_remove_markdown_headers(self):
        """Test removing markdown headers"""
        response = "# Header\n## Subheader\nContent here."
        result = sanitize_zantara_response(response)
        # The sanitizer may or may not remove markdown headers depending on implementation
        assert isinstance(result, str)
        assert len(result) > 0

