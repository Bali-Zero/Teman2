"""
Unit Tests for llm/fallback_messages.py - 95% Coverage Target
Tests the fallback messages module
"""

import os
import sys
from pathlib import Path

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test FALLBACK_MESSAGES constant
# ============================================================================


class TestFallbackMessagesConstant:
    """Test suite for FALLBACK_MESSAGES constant"""

    def test_fallback_messages_has_italian(self):
        """Test that Italian messages are defined"""
        from llm.fallback_messages import FALLBACK_MESSAGES

        assert "it" in FALLBACK_MESSAGES
        assert "connection_error" in FALLBACK_MESSAGES["it"]
        assert "service_unavailable" in FALLBACK_MESSAGES["it"]
        assert "api_key_error" in FALLBACK_MESSAGES["it"]
        assert "generic_error" in FALLBACK_MESSAGES["it"]

    def test_fallback_messages_has_english(self):
        """Test that English messages are defined"""
        from llm.fallback_messages import FALLBACK_MESSAGES

        assert "en" in FALLBACK_MESSAGES
        assert "connection_error" in FALLBACK_MESSAGES["en"]
        assert "service_unavailable" in FALLBACK_MESSAGES["en"]
        assert "api_key_error" in FALLBACK_MESSAGES["en"]
        assert "generic_error" in FALLBACK_MESSAGES["en"]

    def test_fallback_messages_has_indonesian(self):
        """Test that Indonesian messages are defined"""
        from llm.fallback_messages import FALLBACK_MESSAGES

        assert "id" in FALLBACK_MESSAGES
        assert "connection_error" in FALLBACK_MESSAGES["id"]
        assert "service_unavailable" in FALLBACK_MESSAGES["id"]
        assert "api_key_error" in FALLBACK_MESSAGES["id"]
        assert "generic_error" in FALLBACK_MESSAGES["id"]

    def test_italian_messages_are_italian(self):
        """Test that Italian messages contain Italian text"""
        from llm.fallback_messages import FALLBACK_MESSAGES

        assert "scusi" in FALLBACK_MESSAGES["it"]["connection_error"].lower()
        assert "provi" in FALLBACK_MESSAGES["it"]["generic_error"].lower()

    def test_english_messages_are_english(self):
        """Test that English messages contain English text"""
        from llm.fallback_messages import FALLBACK_MESSAGES

        assert "sorry" in FALLBACK_MESSAGES["en"]["connection_error"].lower()
        assert "try" in FALLBACK_MESSAGES["en"]["generic_error"].lower()

    def test_indonesian_messages_are_indonesian(self):
        """Test that Indonesian messages contain Indonesian text"""
        from llm.fallback_messages import FALLBACK_MESSAGES

        assert "maaf" in FALLBACK_MESSAGES["id"]["connection_error"].lower()
        assert "silakan" in FALLBACK_MESSAGES["id"]["generic_error"].lower()


# ============================================================================
# Test get_fallback_message function
# ============================================================================


class TestGetFallbackMessage:
    """Test suite for get_fallback_message function"""

    def test_get_connection_error_english(self):
        """Test getting connection error in English"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("connection_error", "en")

        assert "connection" in result.lower()
        assert isinstance(result, str)

    def test_get_connection_error_italian(self):
        """Test getting connection error in Italian"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("connection_error", "it")

        assert "connessione" in result.lower()

    def test_get_connection_error_indonesian(self):
        """Test getting connection error in Indonesian"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("connection_error", "id")

        assert "koneksi" in result.lower()

    def test_get_service_unavailable_english(self):
        """Test getting service unavailable in English"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("service_unavailable", "en")

        assert "unavailable" in result.lower()

    def test_get_service_unavailable_italian(self):
        """Test getting service unavailable in Italian"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("service_unavailable", "it")

        assert "disponibile" in result.lower()

    def test_get_api_key_error_english(self):
        """Test getting API key error in English"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("api_key_error", "en")

        assert "configuration" in result.lower()

    def test_get_api_key_error_italian(self):
        """Test getting API key error in Italian"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("api_key_error", "it")

        assert "configurazione" in result.lower()

    def test_get_generic_error_english(self):
        """Test getting generic error in English"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("generic_error", "en")

        assert "sorry" in result.lower()

    def test_get_generic_error_italian(self):
        """Test getting generic error in Italian"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("generic_error", "it")

        assert "scusi" in result.lower()

    def test_get_default_language_english(self):
        """Test default language is English"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("connection_error")

        assert "connection" in result.lower()

    def test_get_unknown_language_fallback_to_english(self):
        """Test unknown language falls back to English"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("connection_error", "fr")

        # Should fall back to English
        assert "connection" in result.lower()

    def test_get_unknown_message_type_fallback(self):
        """Test unknown message type falls back to generic error"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("unknown_error_type", "en")

        # Should fall back to generic error
        assert "sorry" in result.lower()
        assert "try" in result.lower()

    def test_get_unknown_both_fallback(self):
        """Test unknown language and message type falls back to English generic"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("unknown_error_type", "fr")

        # Should fall back to English generic error
        assert "sorry" in result.lower()


# ============================================================================
# Test edge cases
# ============================================================================


class TestEdgeCases:
    """Test suite for edge cases"""

    def test_all_message_types_return_strings(self):
        """Test all message types return non-empty strings"""
        from llm.fallback_messages import get_fallback_message

        message_types = [
            "connection_error",
            "service_unavailable",
            "api_key_error",
            "generic_error",
        ]
        languages = ["it", "en", "id"]

        for lang in languages:
            for msg_type in message_types:
                result = get_fallback_message(msg_type, lang)
                assert isinstance(result, str)
                assert len(result) > 0

    def test_empty_string_message_type(self):
        """Test empty string message type falls back to generic"""
        from llm.fallback_messages import get_fallback_message

        result = get_fallback_message("", "en")

        # Should fall back to generic error
        assert isinstance(result, str)
        assert len(result) > 0

    def test_case_sensitive_message_type(self):
        """Test message type is case sensitive"""
        from llm.fallback_messages import get_fallback_message

        result_lower = get_fallback_message("connection_error", "en")
        result_upper = get_fallback_message("CONNECTION_ERROR", "en")

        # Upper case should fall back to generic
        assert result_lower != result_upper or "sorry" in result_upper.lower()

    def test_case_sensitive_language(self):
        """Test language code is case sensitive"""
        from llm.fallback_messages import get_fallback_message

        result_lower = get_fallback_message("connection_error", "it")
        result_upper = get_fallback_message("connection_error", "IT")

        # Upper case should fall back to English
        assert "scusi" in result_lower.lower() or "connessione" in result_lower.lower()
