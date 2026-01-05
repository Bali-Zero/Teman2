"""
Unit tests for Fallback Messages
Target: >99% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from llm.fallback_messages import FALLBACK_MESSAGES, get_fallback_message


class TestFallbackMessages:
    """Tests for FALLBACK_MESSAGES constant"""

    def test_fallback_messages_structure(self):
        """Test that FALLBACK_MESSAGES has expected structure"""
        assert isinstance(FALLBACK_MESSAGES, dict)
        assert "it" in FALLBACK_MESSAGES
        assert "en" in FALLBACK_MESSAGES
        assert "id" in FALLBACK_MESSAGES

    def test_fallback_messages_types(self):
        """Test that each language has expected message types"""
        for lang in ["it", "en", "id"]:
            lang_messages = FALLBACK_MESSAGES[lang]
            assert "connection_error" in lang_messages
            assert "service_unavailable" in lang_messages
            assert "api_key_error" in lang_messages
            assert "generic_error" in lang_messages

    def test_fallback_messages_not_empty(self):
        """Test that messages are not empty"""
        for lang in ["it", "en", "id"]:
            for msg_type in [
                "connection_error",
                "service_unavailable",
                "api_key_error",
                "generic_error",
            ]:
                message = FALLBACK_MESSAGES[lang][msg_type]
                assert isinstance(message, str)
                assert len(message) > 0


class TestGetFallbackMessage:
    """Tests for get_fallback_message function"""

    def test_get_fallback_message_italian(self):
        """Test getting Italian message"""
        result = get_fallback_message("connection_error", "it")
        assert isinstance(result, str)
        assert len(result) > 0
        assert result == FALLBACK_MESSAGES["it"]["connection_error"]

    def test_get_fallback_message_english(self):
        """Test getting English message"""
        result = get_fallback_message("connection_error", "en")
        assert isinstance(result, str)
        assert len(result) > 0
        assert result == FALLBACK_MESSAGES["en"]["connection_error"]

    def test_get_fallback_message_indonesian(self):
        """Test getting Indonesian message"""
        result = get_fallback_message("connection_error", "id")
        assert isinstance(result, str)
        assert len(result) > 0
        assert result == FALLBACK_MESSAGES["id"]["connection_error"]

    def test_get_fallback_message_default_language(self):
        """Test getting message with default language (en)"""
        result = get_fallback_message("connection_error")
        assert isinstance(result, str)
        assert result == FALLBACK_MESSAGES["en"]["connection_error"]

    def test_get_fallback_message_all_types(self):
        """Test getting all message types"""
        for msg_type in [
            "connection_error",
            "service_unavailable",
            "api_key_error",
            "generic_error",
        ]:
            result = get_fallback_message(msg_type, "en")
            assert isinstance(result, str)
            assert len(result) > 0
            assert result == FALLBACK_MESSAGES["en"][msg_type]

    def test_get_fallback_message_invalid_language(self):
        """Test getting message with invalid language (fallback to English)"""
        result = get_fallback_message("connection_error", "invalid_lang")
        assert isinstance(result, str)
        assert result == FALLBACK_MESSAGES["en"]["connection_error"]

    def test_get_fallback_message_invalid_type(self):
        """Test getting message with invalid type (fallback to generic_error)"""
        result = get_fallback_message("invalid_type", "en")
        assert isinstance(result, str)
        assert result == FALLBACK_MESSAGES["en"]["generic_error"]

    def test_get_fallback_message_invalid_language_and_type(self):
        """Test getting message with both invalid language and type"""
        result = get_fallback_message("invalid_type", "invalid_lang")
        assert isinstance(result, str)
        assert result == FALLBACK_MESSAGES["en"]["generic_error"]

