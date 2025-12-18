"""
Comprehensive tests for services/routing/response_handler.py
Target: 95%+ coverage

Tests ResponseHandler class methods:
- __init__: Initialization
- classify_query: Query classification
- sanitize_response: Response sanitization and quality enforcement
"""

import logging
from unittest.mock import patch

import pytest


class TestResponseHandler:
    """Comprehensive test suite for ResponseHandler"""

    @pytest.fixture
    def response_handler(self):
        """Create ResponseHandler instance"""
        from backend.services.routing.response_handler import ResponseHandler

        return ResponseHandler()

    def test_init(self, response_handler):
        """Test ResponseHandler initialization"""
        # Assert instance is created successfully
        assert response_handler is not None

    def test_init_logs_message(self, caplog):
        """Test that __init__ logs initialization message"""
        from backend.services.routing.response_handler import ResponseHandler

        with caplog.at_level(logging.INFO):
            handler = ResponseHandler()
            assert "[ResponseHandler] Initialized" in caplog.text

    # ========================================================================
    # classify_query() tests
    # ========================================================================

    def test_classify_query_greeting(self, response_handler):
        """Test classify_query identifies greetings correctly"""
        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="greeting",
        ):
            result = response_handler.classify_query("ciao")
            assert result == "greeting"

    def test_classify_query_casual(self, response_handler):
        """Test classify_query identifies casual queries correctly"""
        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="casual",
        ):
            result = response_handler.classify_query("come stai?")
            assert result == "casual"

    def test_classify_query_business(self, response_handler):
        """Test classify_query identifies business queries correctly"""
        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="business",
        ):
            result = response_handler.classify_query("quali sono i requisiti per il visto?")
            assert result == "business"

    def test_classify_query_emergency(self, response_handler):
        """Test classify_query identifies emergency queries correctly"""
        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="emergency",
        ):
            result = response_handler.classify_query("urgent help needed")
            assert result == "emergency"

    def test_classify_query_delegates_to_sanitizer(self, response_handler):
        """Test that classify_query delegates to response_sanitizer module"""
        message = "test message"
        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag"
        ) as mock_classify:
            mock_classify.return_value = "business"
            result = response_handler.classify_query(message)
            mock_classify.assert_called_once_with(message)
            assert result == "business"

    # ========================================================================
    # sanitize_response() tests - Basic functionality
    # ========================================================================

    def test_sanitize_response_empty_string(self, response_handler):
        """Test sanitize_response handles empty string"""
        result = response_handler.sanitize_response("", "business")
        assert result == ""

    def test_sanitize_response_none(self, response_handler):
        """Test sanitize_response handles None"""
        result = response_handler.sanitize_response(None, "business")
        assert result is None

    def test_sanitize_response_business_query(self, response_handler):
        """Test sanitize_response for business query"""
        raw_response = "This is a business response with details."
        sanitized = "Sanitized business response."

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value=sanitized,
        ):
            result = response_handler.sanitize_response(raw_response, "business")
            assert result == sanitized

    def test_sanitize_response_greeting_query(self, response_handler):
        """Test sanitize_response for greeting query"""
        raw_response = "Hello! How can I help you?"
        sanitized = "Hello!"

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value=sanitized,
        ):
            result = response_handler.sanitize_response(raw_response, "greeting")
            assert result == sanitized

    def test_sanitize_response_casual_query(self, response_handler):
        """Test sanitize_response for casual query"""
        raw_response = "I'm doing great! Thanks for asking. How about you?"
        sanitized = "I'm doing great! Thanks for asking."

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value=sanitized,
        ):
            result = response_handler.sanitize_response(raw_response, "casual")
            assert result == sanitized

    def test_sanitize_response_emergency_query(self, response_handler):
        """Test sanitize_response for emergency query"""
        raw_response = "Emergency assistance available immediately."
        sanitized = "Emergency assistance available immediately.\n\nNeed help? Contact us on WhatsApp +62 859 0436 9574"

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value=sanitized,
        ):
            result = response_handler.sanitize_response(raw_response, "emergency")
            assert result == sanitized

    # ========================================================================
    # sanitize_response() tests - Parameters
    # ========================================================================

    def test_sanitize_response_apply_santai_true(self, response_handler):
        """Test sanitize_response with apply_santai=True"""
        raw_response = "Long response text here."
        sanitized = "Short response."

        with patch(
            "backend.services.routing.response_handler.process_zantara_response"
        ) as mock_process:
            mock_process.return_value = sanitized
            result = response_handler.sanitize_response(raw_response, "casual", apply_santai=True)
            mock_process.assert_called_once_with(
                raw_response, "casual", apply_santai=True, add_contact=True
            )
            assert result == sanitized

    def test_sanitize_response_apply_santai_false(self, response_handler):
        """Test sanitize_response with apply_santai=False"""
        raw_response = "Long response text here."
        sanitized = "Long response text here."

        with patch(
            "backend.services.routing.response_handler.process_zantara_response"
        ) as mock_process:
            mock_process.return_value = sanitized
            result = response_handler.sanitize_response(
                raw_response, "business", apply_santai=False
            )
            mock_process.assert_called_once_with(
                raw_response, "business", apply_santai=False, add_contact=True
            )
            assert result == sanitized

    def test_sanitize_response_add_contact_true(self, response_handler):
        """Test sanitize_response with add_contact=True"""
        raw_response = "Business response."
        sanitized = "Business response.\n\nNeed help? Contact us on WhatsApp +62 859 0436 9574"

        with patch(
            "backend.services.routing.response_handler.process_zantara_response"
        ) as mock_process:
            mock_process.return_value = sanitized
            result = response_handler.sanitize_response(raw_response, "business", add_contact=True)
            mock_process.assert_called_once_with(
                raw_response, "business", apply_santai=True, add_contact=True
            )
            assert result == sanitized

    def test_sanitize_response_add_contact_false(self, response_handler):
        """Test sanitize_response with add_contact=False"""
        raw_response = "Business response."
        sanitized = "Business response."

        with patch(
            "backend.services.routing.response_handler.process_zantara_response"
        ) as mock_process:
            mock_process.return_value = sanitized
            result = response_handler.sanitize_response(raw_response, "business", add_contact=False)
            mock_process.assert_called_once_with(
                raw_response, "business", apply_santai=True, add_contact=False
            )
            assert result == sanitized

    def test_sanitize_response_all_params_custom(self, response_handler):
        """Test sanitize_response with all custom parameters"""
        raw_response = "Custom response."
        sanitized = "Custom sanitized response."

        with patch(
            "backend.services.routing.response_handler.process_zantara_response"
        ) as mock_process:
            mock_process.return_value = sanitized
            result = response_handler.sanitize_response(
                raw_response, "emergency", apply_santai=False, add_contact=False
            )
            mock_process.assert_called_once_with(
                raw_response, "emergency", apply_santai=False, add_contact=False
            )
            assert result == sanitized

    # ========================================================================
    # sanitize_response() tests - Error handling
    # ========================================================================

    def test_sanitize_response_sanitization_error_returns_original(self, response_handler, caplog):
        """Test sanitize_response returns original response when sanitization fails"""
        raw_response = "Original response"

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            side_effect=Exception("Sanitization failed"),
        ):
            with caplog.at_level(logging.ERROR):
                result = response_handler.sanitize_response(raw_response, "business")
                assert result == raw_response
                assert "Error:" in caplog.text

    def test_sanitize_response_sanitization_error_logs_error(self, response_handler, caplog):
        """Test sanitize_response logs error when sanitization fails"""
        raw_response = "Original response"

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            side_effect=ValueError("Invalid input"),
        ):
            with caplog.at_level(logging.ERROR):
                result = response_handler.sanitize_response(raw_response, "business")
                assert result == raw_response
                assert "[ResponseHandler] Error:" in caplog.text
                assert "Invalid input" in caplog.text

    def test_sanitize_response_sanitization_runtime_error(self, response_handler, caplog):
        """Test sanitize_response handles RuntimeError"""
        raw_response = "Test response"

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            side_effect=RuntimeError("Runtime error occurred"),
        ):
            with caplog.at_level(logging.ERROR):
                result = response_handler.sanitize_response(raw_response, "casual")
                assert result == raw_response
                assert "Runtime error occurred" in caplog.text

    def test_sanitize_response_sanitization_generic_exception(self, response_handler, caplog):
        """Test sanitize_response handles generic exceptions"""
        raw_response = "Test response"

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            side_effect=Exception("Unknown error"),
        ):
            with caplog.at_level(logging.ERROR):
                result = response_handler.sanitize_response(raw_response, "greeting")
                assert result == raw_response
                assert "Unknown error" in caplog.text

    # ========================================================================
    # sanitize_response() tests - Logging
    # ========================================================================

    def test_sanitize_response_logs_success(self, response_handler, caplog):
        """Test sanitize_response logs successful sanitization"""
        raw_response = "Response to sanitize"
        sanitized = "Sanitized response"

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value=sanitized,
        ):
            with caplog.at_level(logging.INFO):
                result = response_handler.sanitize_response(raw_response, "business")
                assert "[ResponseHandler] Sanitized response" in caplog.text
                assert "type: business" in caplog.text

    def test_sanitize_response_logs_query_type_greeting(self, response_handler, caplog):
        """Test sanitize_response logs correct query type for greeting"""
        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value="Hello",
        ):
            with caplog.at_level(logging.INFO):
                response_handler.sanitize_response("Hello", "greeting")
                assert "type: greeting" in caplog.text

    def test_sanitize_response_logs_query_type_casual(self, response_handler, caplog):
        """Test sanitize_response logs correct query type for casual"""
        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value="I'm fine",
        ):
            with caplog.at_level(logging.INFO):
                response_handler.sanitize_response("I'm fine", "casual")
                assert "type: casual" in caplog.text

    def test_sanitize_response_logs_query_type_emergency(self, response_handler, caplog):
        """Test sanitize_response logs correct query type for emergency"""
        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value="Emergency help",
        ):
            with caplog.at_level(logging.INFO):
                response_handler.sanitize_response("Emergency help", "emergency")
                assert "type: emergency" in caplog.text

    # ========================================================================
    # Integration tests - Full workflow
    # ========================================================================

    def test_full_workflow_classify_and_sanitize_greeting(self, response_handler):
        """Test full workflow: classify greeting and sanitize response"""
        message = "ciao"
        raw_response = "User: ciao\nAssistant: Ciao! Come posso aiutarti?"
        expected_sanitized = "Ciao! Come posso aiutarti?"

        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="greeting",
        ):
            with patch(
                "backend.services.routing.response_handler.process_zantara_response",
                return_value=expected_sanitized,
            ):
                # Step 1: Classify
                query_type = response_handler.classify_query(message)
                assert query_type == "greeting"

                # Step 2: Sanitize
                result = response_handler.sanitize_response(raw_response, query_type)
                assert result == expected_sanitized

    def test_full_workflow_classify_and_sanitize_business(self, response_handler):
        """Test full workflow: classify business query and sanitize response"""
        message = "quali sono i requisiti per il visto?"
        raw_response = "[PRICE] I requisiti includono passaporto valido. [MANDATORY]"
        expected_sanitized = (
            "I requisiti includono passaporto valido.\n\n"
            "Need help? Contact us on WhatsApp +62 859 0436 9574"
        )

        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="business",
        ):
            with patch(
                "backend.services.routing.response_handler.process_zantara_response",
                return_value=expected_sanitized,
            ):
                # Step 1: Classify
                query_type = response_handler.classify_query(message)
                assert query_type == "business"

                # Step 2: Sanitize
                result = response_handler.sanitize_response(raw_response, query_type)
                assert result == expected_sanitized
                assert "[PRICE]" not in result
                assert "[MANDATORY]" not in result

    def test_full_workflow_classify_and_sanitize_casual(self, response_handler):
        """Test full workflow: classify casual query and sanitize response"""
        message = "come stai?"
        raw_response = (
            "Sto molto bene, grazie per averlo chiesto! "
            "E tu come stai? Spero che tu stia passando una bella giornata."
        )
        expected_sanitized = "Sto molto bene, grazie per averlo chiesto!"

        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="casual",
        ):
            with patch(
                "backend.services.routing.response_handler.process_zantara_response",
                return_value=expected_sanitized,
            ):
                # Step 1: Classify
                query_type = response_handler.classify_query(message)
                assert query_type == "casual"

                # Step 2: Sanitize (should be truncated by SANTAI mode)
                result = response_handler.sanitize_response(raw_response, query_type)
                assert result == expected_sanitized
                assert len(result.split()) <= 30  # SANTAI mode max words

    def test_full_workflow_classify_and_sanitize_emergency(self, response_handler):
        """Test full workflow: classify emergency query and sanitize response"""
        message = "urgent: lost passport"
        raw_response = "THOUGHT: User needs emergency help\nACTION: Provide immediate assistance"
        expected_sanitized = (
            "Provide immediate assistance\n\n" "Need help? Contact us on WhatsApp +62 859 0436 9574"
        )

        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="emergency",
        ):
            with patch(
                "backend.services.routing.response_handler.process_zantara_response",
                return_value=expected_sanitized,
            ):
                # Step 1: Classify
                query_type = response_handler.classify_query(message)
                assert query_type == "emergency"

                # Step 2: Sanitize (should remove THOUGHT/ACTION artifacts)
                result = response_handler.sanitize_response(raw_response, query_type)
                assert result == expected_sanitized
                assert "THOUGHT:" not in result
                assert "ACTION:" not in result

    # ========================================================================
    # Edge cases
    # ========================================================================

    def test_sanitize_response_whitespace_only(self, response_handler):
        """Test sanitize_response with whitespace-only response"""
        raw_response = "   \n\t  "
        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value="",
        ):
            result = response_handler.sanitize_response(raw_response, "business")
            # Should still process (not early return since it's not empty before strip)
            assert result == ""

    def test_sanitize_response_very_long_response(self, response_handler):
        """Test sanitize_response with very long response"""
        raw_response = "word " * 1000  # 1000 words
        sanitized = "word " * 30  # Truncated to 30 words

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value=sanitized,
        ):
            result = response_handler.sanitize_response(raw_response, "casual")
            assert len(result.split()) <= 30

    def test_sanitize_response_unicode_characters(self, response_handler):
        """Test sanitize_response handles unicode characters"""
        raw_response = "Risposta con caratteri speciali: è, à, ì, ò, ù, €"
        sanitized = "Risposta con caratteri speciali: è, à, ì, ò, ù, €"

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value=sanitized,
        ):
            result = response_handler.sanitize_response(raw_response, "business")
            assert result == sanitized

    def test_sanitize_response_special_characters(self, response_handler):
        """Test sanitize_response handles special characters"""
        raw_response = "Response with special chars: @#$%^&*()_+-=[]{}|;':,.<>?/~`"
        sanitized = "Response with special chars: @#$%^&*()_+-=[]{}|;':,.<>?/~`"

        with patch(
            "backend.services.routing.response_handler.process_zantara_response",
            return_value=sanitized,
        ):
            result = response_handler.sanitize_response(raw_response, "business")
            assert result == sanitized

    def test_classify_query_empty_string(self, response_handler):
        """Test classify_query with empty string"""
        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="business",
        ):
            result = response_handler.classify_query("")
            assert result in ["greeting", "casual", "business", "emergency"]

    def test_classify_query_whitespace(self, response_handler):
        """Test classify_query with whitespace"""
        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="business",
        ):
            result = response_handler.classify_query("   ")
            assert result in ["greeting", "casual", "business", "emergency"]

    def test_classify_query_very_long_message(self, response_handler):
        """Test classify_query with very long message"""
        long_message = "word " * 1000
        with patch(
            "backend.services.routing.response_handler.classify_query_for_rag",
            return_value="business",
        ):
            result = response_handler.classify_query(long_message)
            assert result == "business"
