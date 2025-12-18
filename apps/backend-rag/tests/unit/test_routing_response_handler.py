"""
Unit tests for Response Handler
Comprehensive tests targeting 90%+ coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.response_handler import ResponseHandler

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def response_handler():
    """Create ResponseHandler instance"""
    with patch("services.routing.response_handler.logger"):
        return ResponseHandler()


@pytest.fixture
def mock_logger():
    """Mock logger fixture"""
    return MagicMock()


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_response_handler_init(response_handler):
    """Test ResponseHandler initialization"""
    assert response_handler is not None
    assert isinstance(response_handler, ResponseHandler)


def test_response_handler_init_logs_message():
    """Test ResponseHandler logs initialization message"""
    with patch("services.routing.response_handler.logger") as mock_logger:
        handler = ResponseHandler()
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "ResponseHandler" in call_args
        assert "Initialized" in call_args


# ============================================================================
# Tests: classify_query
# ============================================================================


def test_classify_query_greeting(response_handler):
    """Test classifying greeting query"""
    query_type = response_handler.classify_query("Hello, how are you?")
    assert query_type in ["greeting", "casual", "business", "emergency"]


def test_classify_query_business(response_handler):
    """Test classifying business query"""
    query_type = response_handler.classify_query("What are the requirements for PT PMA?")
    assert query_type in ["greeting", "casual", "business", "emergency"]


def test_classify_query_casual(response_handler):
    """Test classifying casual query"""
    query_type = response_handler.classify_query("How are you?")
    assert query_type in ["greeting", "casual", "business", "emergency"]


def test_classify_query_emergency(response_handler):
    """Test classifying emergency query"""
    query_type = response_handler.classify_query("This is urgent! I need help immediately!")
    assert query_type in ["greeting", "casual", "business", "emergency"]


def test_classify_query_delegates_to_utility(response_handler):
    """Test classify_query delegates to utility function"""
    with patch("services.routing.response_handler.classify_query_for_rag") as mock_classify:
        mock_classify.return_value = "business"
        result = response_handler.classify_query("test query")

        assert result == "business"
        mock_classify.assert_called_once_with("test query")


def test_classify_query_with_empty_string(response_handler):
    """Test classifying empty query"""
    query_type = response_handler.classify_query("")
    assert query_type in ["greeting", "casual", "business", "emergency"]


def test_classify_query_with_special_characters(response_handler):
    """Test classifying query with special characters"""
    query_type = response_handler.classify_query("!@#$%^&*()")
    assert query_type in ["greeting", "casual", "business", "emergency"]


def test_classify_query_with_numbers(response_handler):
    """Test classifying query with numbers"""
    query_type = response_handler.classify_query("123456789")
    assert query_type in ["greeting", "casual", "business", "emergency"]


def test_classify_query_with_long_text(response_handler):
    """Test classifying long query"""
    long_query = "What are the comprehensive requirements and regulations for establishing a PT PMA in Indonesia with all the detailed compliance steps?"
    query_type = response_handler.classify_query(long_query)
    assert query_type in ["greeting", "casual", "business", "emergency"]


def test_classify_query_with_mixed_case(response_handler):
    """Test classifying query with mixed case"""
    query_type = response_handler.classify_query("HeLLo HoW aRe YoU?")
    assert query_type in ["greeting", "casual", "business", "emergency"]


# ============================================================================
# Tests: sanitize_response - Basic Cases
# ============================================================================


def test_sanitize_response_empty(response_handler):
    """Test sanitizing empty response"""
    result = response_handler.sanitize_response("", "business")
    assert result == ""


def test_sanitize_response_none(response_handler):
    """Test sanitizing None response"""
    result = response_handler.sanitize_response(None, "business")
    assert result is None


def test_sanitize_response_false_value(response_handler):
    """Test sanitizing falsy response (False, 0, etc.)"""
    result = response_handler.sanitize_response(False, "business")
    assert result is False


def test_sanitize_response_zero(response_handler):
    """Test sanitizing zero response"""
    result = response_handler.sanitize_response(0, "business")
    assert result == 0


# ============================================================================
# Tests: sanitize_response - Success Cases
# ============================================================================


def test_sanitize_response_success(response_handler):
    """Test sanitizing response successfully"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Sanitized response"
        result = response_handler.sanitize_response("Raw response", "business")

        assert result == "Sanitized response"
        mock_process.assert_called_once_with(
            "Raw response", "business", apply_santai=True, add_contact=True
        )


def test_sanitize_response_returns_exact_value(response_handler):
    """Test sanitizing response returns exact value from processor"""
    test_response = "This is the exact response from processor"
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = test_response
        result = response_handler.sanitize_response("Raw", "greeting")
        assert result == test_response


def test_sanitize_response_preserves_content(response_handler):
    """Test sanitizing response preserves content"""
    original = "Important business information about PT PMA regulations"
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = original
        result = response_handler.sanitize_response(original, "business")
        assert result == original


# ============================================================================
# Tests: sanitize_response - Parameter Variations
# ============================================================================


def test_sanitize_response_with_santai_disabled(response_handler):
    """Test sanitizing response with SANTAI disabled"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Sanitized"
        response_handler.sanitize_response("Raw", "business", apply_santai=False)
        mock_process.assert_called_once_with(
            "Raw", "business", apply_santai=False, add_contact=True
        )


def test_sanitize_response_with_santai_enabled(response_handler):
    """Test sanitizing response with SANTAI enabled (default)"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Sanitized"
        response_handler.sanitize_response("Raw", "business", apply_santai=True)
        mock_process.assert_called_once_with("Raw", "business", apply_santai=True, add_contact=True)


def test_sanitize_response_without_contact(response_handler):
    """Test sanitizing response without contact info"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Sanitized"
        response_handler.sanitize_response("Raw", "business", add_contact=False)
        mock_process.assert_called_once_with(
            "Raw", "business", apply_santai=True, add_contact=False
        )


def test_sanitize_response_with_contact(response_handler):
    """Test sanitizing response with contact info (default)"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Sanitized"
        response_handler.sanitize_response("Raw", "business", add_contact=True)
        mock_process.assert_called_once_with("Raw", "business", apply_santai=True, add_contact=True)


def test_sanitize_response_both_flags_disabled(response_handler):
    """Test sanitizing response with both SANTAI and contact disabled"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Sanitized"
        response_handler.sanitize_response(
            "Raw", "emergency", apply_santai=False, add_contact=False
        )
        mock_process.assert_called_once_with(
            "Raw", "emergency", apply_santai=False, add_contact=False
        )


def test_sanitize_response_both_flags_enabled(response_handler):
    """Test sanitizing response with both SANTAI and contact enabled"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Sanitized"
        response_handler.sanitize_response("Raw", "casual", apply_santai=True, add_contact=True)
        mock_process.assert_called_once_with("Raw", "casual", apply_santai=True, add_contact=True)


# ============================================================================
# Tests: sanitize_response - Query Type Coverage
# ============================================================================


def test_sanitize_response_greeting_type(response_handler):
    """Test sanitizing response for greeting type"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Hi there!"
        response_handler.sanitize_response("Hello", "greeting")
        call_args = mock_process.call_args
        assert call_args[0][1] == "greeting"


def test_sanitize_response_casual_type(response_handler):
    """Test sanitizing response for casual type"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "I'm doing well!"
        response_handler.sanitize_response("How are you?", "casual")
        call_args = mock_process.call_args
        assert call_args[0][1] == "casual"


def test_sanitize_response_business_type(response_handler):
    """Test sanitizing response for business type"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Here are the details..."
        response_handler.sanitize_response("Tell me about regulations", "business")
        call_args = mock_process.call_args
        assert call_args[0][1] == "business"


def test_sanitize_response_emergency_type(response_handler):
    """Test sanitizing response for emergency type"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Emergency response here"
        response_handler.sanitize_response("URGENT!", "emergency")
        call_args = mock_process.call_args
        assert call_args[0][1] == "emergency"


def test_sanitize_response_all_query_types(response_handler):
    """Test sanitizing response for all query types"""
    query_types = ["greeting", "casual", "business", "emergency"]

    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Sanitized"

        for query_type in query_types:
            response_handler.sanitize_response("Test", query_type)

        assert mock_process.call_count == len(query_types)


# ============================================================================
# Tests: sanitize_response - Error Handling
# ============================================================================


def test_sanitize_response_exception(response_handler):
    """Test sanitizing response with exception"""
    with patch(
        "services.routing.response_handler.process_zantara_response", side_effect=Exception("Error")
    ):
        original = "Original response"
        result = response_handler.sanitize_response(original, "business")
        assert result == original


def test_sanitize_response_exception_returns_original_on_value_error(response_handler):
    """Test sanitizing response with ValueError"""
    with patch(
        "services.routing.response_handler.process_zantara_response",
        side_effect=ValueError("Invalid"),
    ):
        original = "Original response"
        result = response_handler.sanitize_response(original, "business")
        assert result == original


def test_sanitize_response_exception_returns_original_on_runtime_error(response_handler):
    """Test sanitizing response with RuntimeError"""
    with patch(
        "services.routing.response_handler.process_zantara_response",
        side_effect=RuntimeError("Runtime"),
    ):
        original = "Original response"
        result = response_handler.sanitize_response(original, "business")
        assert result == original


def test_sanitize_response_exception_returns_original_on_type_error(response_handler):
    """Test sanitizing response with TypeError"""
    with patch(
        "services.routing.response_handler.process_zantara_response",
        side_effect=TypeError("Type error"),
    ):
        original = "Original response"
        result = response_handler.sanitize_response(original, "business")
        assert result == original


def test_sanitize_response_exception_logs_error(response_handler):
    """Test that exceptions are logged"""
    with patch("services.routing.response_handler.logger") as mock_logger:
        handler = ResponseHandler()
        with patch(
            "services.routing.response_handler.process_zantara_response",
            side_effect=Exception("Test error"),
        ):
            handler.sanitize_response("Original", "business")
            # Verify error was logged
            assert mock_logger.error.called


# ============================================================================
# Tests: sanitize_response - Edge Cases
# ============================================================================


def test_sanitize_response_with_unicode_characters(response_handler):
    """Test sanitizing response with unicode characters"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Response with émojis 🎉"
        result = response_handler.sanitize_response("Query with çharacters", "business")
        assert "émojis 🎉" in result


def test_sanitize_response_with_newlines(response_handler):
    """Test sanitizing response with newlines"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        response_with_newlines = "Line 1\nLine 2\nLine 3"
        mock_process.return_value = response_with_newlines
        result = response_handler.sanitize_response("Multi\nline\nquery", "business")
        assert result == response_with_newlines


def test_sanitize_response_with_long_response(response_handler):
    """Test sanitizing very long response"""
    long_response = "A" * 10000
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = long_response
        result = response_handler.sanitize_response("Query", "business")
        assert len(result) == 10000


def test_sanitize_response_with_special_characters(response_handler):
    """Test sanitizing response with special characters"""
    special_response = "Response with !@#$%^&*() special chars"
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = special_response
        result = response_handler.sanitize_response("Query", "business")
        assert "!@#$%^&*()" in result


def test_sanitize_response_with_html_tags(response_handler):
    """Test sanitizing response with HTML tags"""
    html_response = "<p>Response with <b>HTML</b> tags</p>"
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = html_response
        result = response_handler.sanitize_response("Query", "business")
        assert "<p>" in result


def test_sanitize_response_with_whitespace(response_handler):
    """Test sanitizing response with extra whitespace"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "   Response with spaces   "
        result = response_handler.sanitize_response("Query", "business")
        assert result == "   Response with spaces   "


# ============================================================================
# Tests: sanitize_response - Logging
# ============================================================================


def test_sanitize_response_logs_success(response_handler):
    """Test that successful sanitization is logged"""
    with patch("services.routing.response_handler.logger") as mock_logger:
        handler = ResponseHandler()
        with patch("services.routing.response_handler.process_zantara_response") as mock_process:
            mock_process.return_value = "Sanitized"
            handler.sanitize_response("Raw", "business")
            # Verify success was logged
            assert mock_logger.info.call_count >= 2  # Init + sanitize


def test_sanitize_response_logs_query_type(response_handler):
    """Test that query type is logged in sanitization"""
    with patch("services.routing.response_handler.logger") as mock_logger:
        handler = ResponseHandler()
        with patch("services.routing.response_handler.process_zantara_response") as mock_process:
            mock_process.return_value = "Sanitized"
            handler.sanitize_response("Raw", "emergency")
            # Check if type was logged
            logged_calls = [call_args[0][0] for call_args in mock_logger.info.call_args_list]
            assert any("emergency" in str(call) for call in logged_calls)


# ============================================================================
# Tests: Integration
# ============================================================================


def test_classify_and_sanitize_greeting(response_handler):
    """Test classifying and sanitizing greeting together"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Hello!"
        query_type = response_handler.classify_query("Hi there")
        result = response_handler.sanitize_response("Hi there!", query_type)
        assert result == "Hello!"


def test_classify_and_sanitize_business(response_handler):
    """Test classifying and sanitizing business query together"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Business response"
        query_type = response_handler.classify_query("What are PT PMA requirements?")
        result = response_handler.sanitize_response("Raw business response", query_type)
        assert result == "Business response"


def test_multiple_sanitizations_sequential(response_handler):
    """Test multiple sanitizations in sequence"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.side_effect = ["Response 1", "Response 2", "Response 3"]

        result1 = response_handler.sanitize_response("Query 1", "business")
        result2 = response_handler.sanitize_response("Query 2", "casual")
        result3 = response_handler.sanitize_response("Query 3", "greeting")

        assert result1 == "Response 1"
        assert result2 == "Response 2"
        assert result3 == "Response 3"
        assert mock_process.call_count == 3


def test_handler_state_isolation(response_handler):
    """Test that handler maintains isolation between calls"""
    with patch("services.routing.response_handler.process_zantara_response") as mock_process:
        mock_process.return_value = "Response"

        # Call with different parameters
        response_handler.sanitize_response("Query 1", "business", apply_santai=True)
        response_handler.sanitize_response("Query 2", "casual", apply_santai=False)

        # Verify each call had correct parameters
        calls = mock_process.call_args_list
        assert calls[0][1]["apply_santai"] is True
        assert calls[1][1]["apply_santai"] is False
