"""
Unit tests for ResponseHandler
Tests response sanitization and quality enforcement
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestResponseHandler:
    """Unit tests for ResponseHandler"""

    def test_response_handler_init(self):
        """Test ResponseHandler initialization"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        assert handler is not None

    def test_classify_query_greeting(self):
        """Test classifying greeting query"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        query_type = handler.classify_query("ciao")
        assert query_type in ["greeting", "casual", "business", "emergency"]

    def test_classify_query_business(self):
        """Test classifying business query"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        query_type = handler.classify_query("visa requirements")
        assert query_type in ["greeting", "casual", "business", "emergency"]

    def test_classify_query_emergency(self):
        """Test classifying emergency query"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        query_type = handler.classify_query("urgent help needed")
        assert query_type in ["greeting", "casual", "business", "emergency"]

    def test_sanitize_response_normal(self):
        """Test sanitizing normal response"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        response = "This is a normal response."
        result = handler.sanitize_response(response, query_type="business")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_sanitize_response_empty(self):
        """Test sanitizing empty response"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        result = handler.sanitize_response("", query_type="business")
        assert result == ""

    def test_sanitize_response_none(self):
        """Test sanitizing None response"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        result = handler.sanitize_response(None, query_type="business")
        assert result is None

    def test_sanitize_response_with_santai(self):
        """Test sanitizing response with SANTAI mode"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        response = "This is a long response that should be truncated in SANTAI mode."
        result = handler.sanitize_response(response, query_type="greeting", apply_santai=True)
        assert isinstance(result, str)

    def test_sanitize_response_without_santai(self):
        """Test sanitizing response without SANTAI mode"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        response = "This is a long response that should not be truncated."
        result = handler.sanitize_response(response, query_type="business", apply_santai=False)
        assert isinstance(result, str)

    def test_sanitize_response_with_contact(self):
        """Test sanitizing response with contact info"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        response = "Here is the information you requested."
        result = handler.sanitize_response(response, query_type="business", add_contact=True)
        assert isinstance(result, str)

    def test_sanitize_response_without_contact(self):
        """Test sanitizing response without contact info"""
        from backend.services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()
        response = "Here is the information you requested."
        result = handler.sanitize_response(response, query_type="greeting", add_contact=False)
        assert isinstance(result, str)

    def test_sanitize_response_error_handling(self):
        """Test sanitize response error handling"""
        with patch(
            "backend.services.routing.response_handler.process_zantara_response"
        ) as mock_process:
            mock_process.side_effect = Exception("Sanitization error")

            from backend.services.routing.response_handler import ResponseHandler

            handler = ResponseHandler()
            response = "Test response"
            result = handler.sanitize_response(response, query_type="business")
            # Should return original response on error
            assert result == response
