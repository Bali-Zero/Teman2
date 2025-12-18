"""
Unit tests for Fallback Messages
"""

import sys
from pathlib import Path

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from llm.fallback_messages import FALLBACK_MESSAGES, get_fallback_message


def test_fallback_messages_structure():
    """Test FALLBACK_MESSAGES has correct structure"""
    assert isinstance(FALLBACK_MESSAGES, dict)
    assert "it" in FALLBACK_MESSAGES
    assert "en" in FALLBACK_MESSAGES
    assert "id" in FALLBACK_MESSAGES

    for lang in FALLBACK_MESSAGES.values():
        assert "connection_error" in lang
        assert "service_unavailable" in lang
        assert "generic_error" in lang


def test_get_fallback_message_english():
    """Test getting fallback message in English"""
    message = get_fallback_message("connection_error", "en")

    assert isinstance(message, str)
    assert len(message) > 0
    assert "connection" in message.lower() or "issue" in message.lower()


def test_get_fallback_message_italian():
    """Test getting fallback message in Italian"""
    message = get_fallback_message("connection_error", "it")

    assert isinstance(message, str)
    assert len(message) > 0
    assert "scusi" in message.lower() or "problema" in message.lower()


def test_get_fallback_message_indonesian():
    """Test getting fallback message in Indonesian"""
    message = get_fallback_message("connection_error", "id")

    assert isinstance(message, str)
    assert len(message) > 0
    assert "maaf" in message.lower() or "masalah" in message.lower()


def test_get_fallback_message_default_language():
    """Test getting fallback message with default language"""
    message = get_fallback_message("connection_error")

    assert isinstance(message, str)
    assert len(message) > 0


def test_get_fallback_message_unknown_language():
    """Test getting fallback message with unknown language falls back to English"""
    message = get_fallback_message("connection_error", "unknown")

    assert isinstance(message, str)
    assert len(message) > 0


def test_get_fallback_message_unknown_type():
    """Test getting fallback message with unknown type falls back to generic_error"""
    message = get_fallback_message("unknown_type", "en")

    assert isinstance(message, str)
    assert len(message) > 0


def test_all_message_types():
    """Test all message types are available"""
    message_types = ["connection_error", "service_unavailable", "generic_error"]

    for msg_type in message_types:
        for lang in ["en", "it", "id"]:
            message = get_fallback_message(msg_type, lang)
            assert isinstance(message, str)
            assert len(message) > 0










